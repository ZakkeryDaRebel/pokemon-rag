# Description

This code utilizes a database based on information on the HeartGold / SoulSilver 
generation of Pokemon Games. Utilizing this information, a user's question is
passed to AI (in my case Gemini since it has a free API key) to create a
SQLLite SELECT statement to query my database. Then the result of the query
is returned back to AI to create a friendly response to return back to the user.

Most of this code is the base code given from Professor Reynolds or generated
using Codex.

> [!WARNING]
> If you plan on using this code, note that Gemini's free API key
usually only lasts for about 5 or so questions to be asked to it, meaning you
will either want to have multiple accounts with multiple API keys if you want
to run this quite a few times, or you will want to swap to using a different
AI API key (such as back to OpenAI) if wanted.

## Database Schema Picture

![Schema](./database_schema.png)
