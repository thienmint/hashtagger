from pony.orm import *

db = Database()


class User(db.Entity):
    username = Required(str, unique=True)
    password = Required(str)
    hashtag = Required(str)
    message = Required(Json)
    verified = Required(bool)
    history = Required(Json)


db.bind(provider='sqlite', filename='users.db', create_db=True)
db.generate_mapping(create_tables=True)
