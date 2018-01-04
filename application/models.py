from pony.orm import *
import os
db = Database()


class User(db.Entity):
    username = Required(str, unique=True)
    password = Required(str)
    hashtag = Required(str)
    message = Required(Json)
    verified = Required(bool)
    history = Required(Json)


# db.bind(provider='sqlite', filename='users.db', create_db=True)
db.bind(provider='postgres',
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PW'],
        host=os.environ['POSTGRES_HOST'],
        database=os.environ['POSTGRES_DB'])
db.generate_mapping(create_tables=True)
