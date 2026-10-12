create table trainer (
    trainer_id integer primary key,
    name varchar(20) not null,
    gym_badge_count integer
);

create table type (
    type_id integer primary key,
    name varchar(20) not null
);

create table pokedex (
    pokemon_id integer primary key,
    name varchar(30) not null,
    base_speed integer not null,
    base_hp integer not null,
    base_physical_attack integer not null,
    base_special_attack integer not null,
    base_physical_defense integer not null,
    base_special_defense integer not null,
    type1 integer not null,
    type2 integer,
    foreign key (type1) references type (type_id),
    foreign key (type2) references type (type_id)
);

create table evolution (
    evolution_id integer primary key,
    original_form_id integer,
    evolution_form_id integer,
    evolution_level integer not null,
    method text not null check (method in (
        'level_up', 'use_item', 'trade', 'friendship',
        'move_known', 'special'
    )),
    minimum_level integer,
    condition text,
    foreign key (original_form_id) references pokedex (pokemon_id),
    foreign key (evolution_form_id) references pokedex (pokemon_id)
);

create table effectiveness (
    defender_type integer,
    attacker_type integer,
    modifier real not null, --0, 0.5, or 2
    primary key (defender_type, attacker_type),
    foreign key (defender_type) references type (type_id),
    foreign key (attacker_type) references type (type_id)
);

create table nature (
    nature_id integer primary key,
    nature_name varchar(20) not null unique,
    plus_stat varchar(25) not null,
    negative_stat varchar(25) not null
);

create table moves (
    move_id integer primary key,
    name varchar(30) not null,
    description text not null,
    power integer,
    move_type varchar(8) check(move_type in ('physical', 'special', 'status')),
    type integer,
    pp integer,
    foreign key (type) references type (type_id)
);

create table ability (
    ability_id integer primary key,
    name varchar(30) not null unique,
    description text not null
);

create table pc (
    trainer_id integer,
    pokemon_id integer,
    catch_id integer,
    nickname varchar(20),
    gender char(7) check (gender in ('Male', 'Female', 'Unknown')),
    ability integer,
    move1 integer,
    move2 integer,
    move3 integer,
    move4 integer,
    level integer,
    nature integer,
    primary key (trainer_id, catch_id),
    foreign key (trainer_id) references trainer (trainer_id),
    foreign key (pokemon_id) references pokedex (pokemon_id),
    foreign key (ability) references ability (ability_id),
    foreign key (move1) references moves (move_id),
    foreign key (move2) references moves (move_id),
    foreign key (move3) references moves (move_id),
    foreign key (move4) references moves (move_id),
    foreign key (nature) references nature (nature_id)
);

--create table person (
--    person_id integer primary key,
--    name varchar(20) not null
--);
--
--create table phone (
--    phone_id integer primary key,
--    person_id integer not null,
--    area_code int not null,
--    number int not null,
--    can_recieve_sms tinyint not null,
--    foreign key (person_id) references person (person_id)
--);
--
--create table address (
--    address_id integer primary key,
--    person_id integer not null,
--    street varchar(50),
--    zip integer not null
--);
--
--create table zip (
--    zip integer primary key,
--    city varchar(35),
--    state_two_letter_code char(2)
--);
--
--create table dog (
--    dog_id integer primary key,
--    name varchar(35),
--    breed varchar(35),
--    birth_date date
--);
--
--create table award (
--    award_id integer primary key,
--    dog_id integer not null,
--    event_date date,
--    award_name varchar(25) not null,
--    foreign key (dog_id) references dog (dog_id)
--);
--
--create table person_dog (
--    dog_id integer,
--    person_id integer,
--    foreign key (dog_id) references dog (dog_id),
--    foreign key (person_id) references person (person_id)
--);
