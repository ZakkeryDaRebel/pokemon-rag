import json
from google import genai
import os
import random
import sqlite3
from time import sleep, time

print("Running db_bot.py!")

fdir = os.path.dirname(__file__)
def getPath(fname):
    return os.path.join(fdir, fname)

# SQLITE
setupSqlPath = getPath("setup.sql")
setupSqlDataPath = getPath("setupData.sql")

# Erase previous db
if os.path.exists(sqliteDbPath):
    os.remove(sqliteDbPath)

# create new db
sqliteCon = sqlite3.connect(sqliteDbPath)
sqliteCursor = sqliteCon.cursor()

# read in setup files
with (
        open(setupSqlPath) as setupSqlFile,
        open(setupSqlDataPath) as setupSqlDataFile
    ):

    setupSqlScript = setupSqlFile.read()
    setupSQlDataScript = setupSqlDataFile.read()

# execute setup files
sqliteCursor.executescript(setupSqlScript) # setup tables and keys
sqliteCursor.executescript(setupSQlDataScript) # setup tables and keys

# Deterministic Pokémon helpers make generated SQL less dependent on Gemini
# reproducing multi-step arithmetic correctly.
effectivenessByPair = {
    (attackerType, defenderType): modifier
    for attackerType, defenderType, modifier in sqliteCursor.execute(
        "SELECT attacker_type, defender_type, modifier FROM effectiveness"
    ).fetchall()
}

def pokemonHpStat(baseHp, level):
    if baseHp is None or level is None:
        return None
    return ((2 * int(baseHp) * int(level)) // 100) + int(level) + 10

def pokemonStatAtLevel(baseStat, level, plusStat, negativeStat, statName):
    if None in (baseStat, level, statName):
        return None
    statBeforeNature = ((2 * int(baseStat) * int(level)) // 100) + 5
    natureMultiplier = 1.1 if plusStat == statName else 0.9 if negativeStat == statName else 1.0
    return int(statBeforeNature * natureMultiplier)

def pokemonTypeEffectiveness(moveType, defenderType1, defenderType2):
    if moveType is None or defenderType1 is None:
        return None
    multiplier = effectivenessByPair.get((int(moveType), int(defenderType1)), 1.0)
    if defenderType2 is not None:
        multiplier *= effectivenessByPair.get((int(moveType), int(defenderType2)), 1.0)
    return multiplier

def pokemonStab(moveType, attackerType1, attackerType2):
    if moveType is None:
        return None
    return 1.5 if moveType in (attackerType1, attackerType2) else 1.0

def pokemonDamage(level, power, attack, defense, effectiveness, stab):
    if None in (level, power, attack, defense, effectiveness, stab) or defense == 0:
        return None
    level, power, attack, defense = map(int, (level, power, attack, defense))
    baseDamage = (((2 * level) // 5 + 2) * power * attack / defense / 50)
    return int((int(baseDamage) + 2) * float(effectiveness) * float(stab))

sqliteCon.create_function("pokemon_hp_stat", 2, pokemonHpStat)
sqliteCon.create_function("pokemon_stat_at_level", 5, pokemonStatAtLevel)
sqliteCon.create_function("pokemon_type_effectiveness", 3, pokemonTypeEffectiveness)
sqliteCon.create_function("pokemon_stab", 3, pokemonStab)
sqliteCon.create_function("pokemon_damage", 6, pokemonDamage)

def runSql(query):
    result = sqliteCursor.execute(query).fetchall()
    return result

# OPENAI
configPath = getPath("config.json")
print(configPath)
with open(configPath) as configFile:
    config = json.load(configFile)

#openAiClient = OpenAI(api_key = config["openaiKey"])
geminiClient = genai.Client(api_key=config["geminiKey"])
#openAiClient.models.list() # check if the key is valid (update in config.json)
chosen_model = "gemini-3.8-flash"

def isGemini503Error(err):
    """Recognize a transient Gemini 503 across SDK exception versions."""
    statusCode = (
        getattr(err, "status_code", None)
        or getattr(err, "code", None)
        or getattr(getattr(err, "response", None), "status_code", None)
    )
    return statusCode == 503 or "503" in str(err) or "UNAVAILABLE" in str(err)

def getGeminiResponse(content):
    # The SDK retries transient errors itself. These bounded outer retries give
    # a final 503 another chance without allowing the script to wait forever.
    max503Retries = 3
    for attempt in range(max503Retries + 1):
        try:
            response = geminiClient.models.generate_content(
                model=chosen_model,
                contents=content
            )
            return response.text or ""
        except Exception as err:
            if not isGemini503Error(err) or attempt == max503Retries:
                raise
            delay = min(2 ** attempt + random.uniform(0, 0.5), 8)
            print(
                f"Gemini returned 503; retrying in {delay:.1f}s "
                f"({attempt + 1}/{max503Retries})..."
            )
            sleep(delay)

    # responseList = []
    # for chunk in stream:
    #     if chunk.choices[0].delta.content is not None:
    #         responseList.append(chunk.choices[0].delta.content)
    #
    # result = "".join(responseList)
    # return result


pokemonSqlGuidance = """

Pokémon database rules and calculations:
- A Pokémon's base stat total (BST) is the sum of pokedex.base_speed,
  base_hp, base_physical_attack, base_special_attack,
  base_physical_defense, and base_special_defense. Use these exact column
  names; the schema calls it physical_defense, not psychical_defense.
- In moves, move_type is the damage class ('physical', 'special', or
  'status'); type is the move's elemental type ID. In pokedex, type1 and
  type2 are the defender's elemental type IDs. In effectiveness,
  attacker_type is the attacking move type and defender_type is one of the
  defending Pokémon's types. Prefer the registered SQL helper
  pokemon_type_effectiveness(move_type_id, defender_type1_id, defender_type2_id).
  It multiplies dual-type modifiers and treats a missing row or NULL type2
  as 1.0. A combined multiplier >= 2 is super effective;
  a multiplier <= 0.5 is not very effective; 0 means immune.
- A Pokémon's level and nature are stored on pc. Join pc.nature to
  nature.nature_id to get nature.plus_stat and nature.negative_stat.
  Nature stat values are 'physical_attack', 'special_attack',
  'physical_defense', 'special_defense', and 'speed'; neutral natures store
  'none'. There are no IV or EV columns, so assume IV=0 and EV=0 unless the
  question supplies another rule.
- Prefer the registered SQL helper pokemon_hp_stat(base_hp, level) for HP
  and pokemon_stat_at_level(base_stat, level, plus_stat, negative_stat,
  stat_name) for another stat. These helpers implement
  floor((2*base*level)/100)+level+10 for HP and
  floor((floor((2*base*level)/100)+5)*nature_multiplier) for another stat.
  Nature multiplier is 1.1 when plus_stat matches, 0.9 when negative_stat
  matches, and 1.0 otherwise. HP is not modified by nature. These helpers
  assume IV=0 and EV=0.
- For move damage, use moves.power, moves.move_type, and moves.type.
  Physical moves use the attacker's base/current physical attack and the
  defender's physical defense; special moves use special attack and special
  defense. When a combatant has a matching pc row, calculate its attack or
  defense at that row's level using the nature rule above. Use a level and
  nature supplied in the question when the combatant has no pc row; do not
  invent missing levels. Prefer pokemon_stab(move_type_id, user_type1_id,
  user_type2_id) for STAB and pokemon_damage(level, power, attack, defense,
  effectiveness, stab) for damage. pokemon_damage implements the simplified
  deterministic formula floor((floor(2*level/5)+2)*power*attack/defense/50)
  + 2, followed by effectiveness and STAB. This omits random damage,
  critical hits, burn, weather, and other battle modifiers. Do not calculate
  damage for status moves or moves whose power is NULL.
- To get a trainer's Pokémon, join trainer to pc on trainer_id and pc to
  pokedex on pokemon_id. For move slots, join moves against pc.move1 through
  pc.move4 and ignore NULL slots.
"""

commonSqlOnlyRequest = "\nReturn exactly one valid SQLite SELECT statement that answers the question. Do not include markdown, comments, or explanations."
schemaForPrompt = "\n".join(
    line for line in setupSqlScript.splitlines()
    if not line.lstrip().startswith("--")
)
basePokemonPrompt = schemaForPrompt + pokemonSqlGuidance

# Strategies
strategies = {
    "zero_shot": basePokemonPrompt + commonSqlOnlyRequest,
    "single_domain_double_shot": (
        basePokemonPrompt
        + "\n\nExample 1\n"
        + "Question: What are the five Pokémon with the highest BST?\n"
        + "SQL: SELECT name, base_speed + base_hp + base_physical_attack + "
          "base_special_attack + base_physical_defense + base_special_defense "
          "AS bst FROM pokedex ORDER BY bst DESC, pokemon_id LIMIT 5;\n\n"
        + "Example 2\n"
        + "Question: What is the type multiplier for an Ice move against a Dragon/Flying Pokémon?\n"
        + "SQL: SELECT pokemon_type_effectiveness("
          "(SELECT type_id FROM type WHERE name = 'Ice'), "
          "(SELECT type_id FROM type WHERE name = 'Dragon'), "
          "(SELECT type_id FROM type WHERE name = 'Flying')) AS effectiveness;\n"
        + commonSqlOnlyRequest
    )
    # TODO add strategies as described in the paper (multi-domain)
}

questions = [
    # "What are the top 5 pokemon with the highest bst?"
    # ,
    # "List the 3 highest speed pokemon in Red's box."
    # ,
    # "What pokemon does Red still need to catch and put into his box?"
    # ,
    # "What move should Tristan's Cyndaquil use to one shot a level 1 caterpie?"
    # ,
    # "If Red is going to fight a new trainer called Misty that has a Kingdra with Hydro Pump, Dragon Dance, Dragon Pulse, and Blizzard, and a Starmie with Swift, Aqua Jet, Surf, and Recover, what are the 3 best offensive pokemon he could bring and the 3 best defensive pokemon he could bring?"
    # ,
    # "Which Pokémon does Tristan have in their PC, and what are each Pokémon’s type(s), level, ability, nature, and moves?"
    # ,
    "What Pokemon does Tristan have that can evolve and how or when can they evolve?"
]


# use the markdown for the sql syntax to find the SQL query
def sanitizeForJustSql(value):
    gptStartSqlMarker = "```"
    gptEndSqlMarker = "```"
    if gptStartSqlMarker in value:
        # Split at the first ``` and take everything after it
        value = value.split(gptStartSqlMarker, 1)[1]
        # Find the newline after the language identifier (sql, sqlite, etc.)
        newline_index = value.find("\n")
        if newline_index != -1:
            value = value[newline_index + 1:]
    if gptEndSqlMarker in value:
        # Split at the closing ``` and take everything before it
        value = value.split(gptEndSqlMarker, 1)[0]

    return value.strip()

for strategy in strategies:
    responses = {"strategy": strategy, "prompt_prefix": strategies[strategy]}
    questionResults = []
    print("########################################################################")
    print(f"Running strategy: {strategy}")
    for question in questions:

        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("Question:")
        print(question)
        error = "None"
        sqlSyntaxResponse = ""
        queryRawResponse = ""
        friendlyResponse = ""
        try:
            getSqlFromQuestionEngineeredPrompt = strategies[strategy] + " " + question
            sqlSyntaxResponse = getGeminiResponse(getSqlFromQuestionEngineeredPrompt)
            sqlSyntaxResponse = sanitizeForJustSql(sqlSyntaxResponse)
            print("SQL Syntax Response:")
            print(sqlSyntaxResponse)
            queryRawResponse = str(runSql(sqlSyntaxResponse))
            print("Query Raw Response:")
            print(queryRawResponse)
        except Exception as err:
            error = f"SQL generation/query failed: {err}"
            print(error)

        # Keep the successful SQL result even if the separate friendly-text
        # request fails. The raw result is a useful local fallback and avoids
        # losing the answer just because Gemini's second call was unavailable.
        if queryRawResponse:
            friendlyResultsPrompt = (
                f'I asked a question "{question}" and the response was '
                f'"{queryRawResponse}". Please give a concise, friendly '
                "response without extra suggestions or chatter."
            )
            try:
                friendlyResponse = getGeminiResponse(friendlyResultsPrompt)
            except Exception as err:
                friendlyResponse = queryRawResponse
                friendlyError = f"Friendly response generation failed: {err}"
                error = friendlyError if error == "None" else f"{error}; {friendlyError}"
                print(friendlyError)
            print("Friendly Response:")
            print(friendlyResponse)
        elif not friendlyResponse:
            friendlyResponse = "The question could not be completed. See the error field for details."

        questionResults.append({
            "question": question,
            "sql": sqlSyntaxResponse,
            "queryRawResponse": queryRawResponse,
            "friendlyResponse": friendlyResponse,
            "error": error
        })

    responses["questionResults"] = questionResults

    with open(getPath(f"response_{strategy}_{time()}.json"), "w") as outFile:
        json.dump(responses, outFile, indent = 2)


sqliteCursor.close()
sqliteCon.close()
print("Done!")
