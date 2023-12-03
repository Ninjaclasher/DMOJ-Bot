import peewee as db

import settings

database = db.SqliteDatabase(settings.DATABASE_FILE)


class BaseModel(db.Model):
    class Meta:
        database = database


class User(BaseModel):
    discord_id = db.BigIntegerField(unique=True)
    dmoj_id = db.BigIntegerField(unique=True, null=True)
    username = db.CharField(null=True, default=None)
    rating = db.IntegerField(null=True, default=None)

    @property
    def is_linked(self):
        return self.dmoj_id is not None
