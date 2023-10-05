# Django Cache With MongoDB

## Installation and Usage

Install with:

    $ pip install django-cache-with-mongodb

Add the following to your Django settings::

    CACHES = {
        'default': {
            'BACKEND': 'django_cache_with_mongodb.MongoDBCache',
            "LOCATION": "[mongodb://][username:password@]host1[:port1][,...hostN[:portN]][/[defaultdb][?options]]",
            "OPTIONS": {
                "USERNAME": "username_if_desired",
                "PASSWORD": "password_if_needed",
                "DATABASE": "cache_db_name",  # in not supplied in URI
                "COLLECTION": "cache_colleciton",  # default: django_cache
                # Any Connection Options supported by pymongo
            },
            "TIMEOUT": 86400, # either set TIMEOUT or MAX_ENTRIES, not both
            "MAX_ENTRIES": 10000, # either set MAX_ENTRIES or TIMEOUT, not both
        }
    }

### LOCATION

Location supports MongoDB [Connection String](https://www.mongodb.com/docs/manual/reference/connection-string/). Additionally, any supported pymongo parameters could be 

### OPTIONS

Any supported [pymongo parameters](https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html) could be added to OPTIONS.

## Notice

The backend will handle TTL index creation if TIMEOUT is set, or will create a capped collection if MAX_ENTRIES is set. You should ensure that the collections are not created beforehands, so that the backend can do its work correctly.
