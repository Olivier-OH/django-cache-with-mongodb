# -*- coding: utf-8 -*-
# Author:
#  Karol Sikora <karol.sikora@laboratorium.ee>, (c) 2012
#  Alireza Savand <alireza.savand@gmail.com>, (c) 2013, 2014, 2015
#  Olivier Hoareau <olivier.p.hoareau@gmail.com>, (c) 2018
#  Sergey Romanyuk (https://github.com/romanukes), (c) 2023

from __future__ import print_function, unicode_literals

try:
    import cPickle as pickle
except ImportError:
    import pickle

import base64
import functools
import re
from datetime import timedelta

import bson
import pymongo
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from pymongo.errors import ExecutionTimeout, OperationFailure


def reconnect(retries=3):
    def _decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            tries = 0
            while tries < retries:
                try:
                    return f(*args, **kwargs)
                except pymongo.errors.AutoReconnect:
                    tries += 1
            raise pymongo.errors.ConnectionFailure(
                "Could not reconnect to mongodb after {} retries.".format(retries)
            )

        return wrapper

    return _decorator


class MongoDBCache(BaseCache):
    def __init__(self, location, params):
        options = params.get("OPTIONS", {})

        if "timeout" not in params and "TIMEOUT" not in params:
            params["TIMEOUT"] = None
        if "max_entries" not in params and "MAX_ENTRIES" not in options:
            params["max_entries"] = -1

        BaseCache.__init__(self, params)

        self._host = "localhost:27017"
        self._database = None
        self._username = None
        self._password = None
        self._collection_name = "django_cache"
        self._connection_options = {}
        self._tz_aware = getattr(settings, "USE_TZ", False)

        # update conf with mongo uri data, only if uri was given
        if location:
            url = location

            if not url.startswith("mongodb://"):
                url = "mongodb://" + url

            uri_data = pymongo.uri_parser.parse_uri(url)
            # build the hosts list to create a mongo connection
            hosts_list = [f"{x[0]}:{x[1]}" for x in uri_data["nodelist"]]
            self._username = uri_data["username"]
            self._password = uri_data["password"]
            self._host = hosts_list
            if uri_data["database"]:
                # if no database is provided in the uri, use default
                self._database = uri_data["database"]

            self._connection_options.update(uri_data["options"])

        # update connection_options with specific settings
        if options:
            config = dict(options)  # don't modify original

            self._username = config.pop("USERNAME", self._username)
            self._password = config.pop("PASSWORD", self._password)
            self._database = config.pop("DATABASE", self._database)
            self._collection_name = config.pop("COLLECTION", "django_cache")

            self._connection_options.update(config)

        self._connection_options["host"] = self._host
        self._connection_options["tz_aware"] = self._tz_aware
        if self._username:
            self._connection_options["username"] = self._username
        if self._password:
            self._connection_options["password"] = self._password

        if self._max_entries is not None and self._max_entries <= 0:
            self._max_entries = None

        if self.default_timeout is not None and self.default_timeout <= 0:
            self.default_timeout = None

        if self.default_timeout is not None and self._max_entries is not None:
            raise ImproperlyConfigured(
                "MongoDBCache shall be configured either with TIMEOUT or MAX_ENTRIES, not both."
            )

        if self.default_timeout is None and self._max_entries is None:
            raise ImproperlyConfigured(
                "MongoDBCache shall be configured with TIMEOUT or MAX_ENTRIES. Specify one or the other."
            )

    def make_key(self, key, version=None):
        """
        Additional regexp to remove $ and . characters,
        as they cause special behaviour in mongodb
        """
        key = super(MongoDBCache, self).make_key(key, version)

        return re.sub(r"\$|\.", "_", key)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_key(key, version)
        self.validate_key(key)

        return self._base_set("add", key, value, timeout)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_key(key, version)
        self.validate_key(key)

        return self._base_set("set", key, value, timeout)

    @reconnect()
    def _base_set(self, mode, key, value, timeout=DEFAULT_TIMEOUT):
        if timeout is DEFAULT_TIMEOUT:
            timeout = self.default_timeout

        now = timezone.now()
        if timeout not in (None, -1):
            expires = now + timedelta(seconds=timeout)
        else:
            expires = None
        coll = self._get_collection()

        if mode == "add" and self.has_key(key):
            return False

        try:
            try:
                coll.update_one(
                    {"key": key},
                    {
                        "$set": {"data_raw": value, "expires": expires, "last_change": now},
                        "$unset": {"data": ""},
                    },
                    upsert=True,
                )
            except bson.errors.InvalidDocument:
                pickled = pickle.dumps(value, pickle.HIGHEST_PROTOCOL)
                encoded = base64.encodebytes(pickled).strip()
                coll.update_one(
                    {"key": key},
                    {
                        "$set": {
                            "data": encoded,
                            "expires": expires,
                            "last_change": now,
                        },
                        "$unset": {"data_raw": ""},
                    },
                    upsert=True,
                )
        except (OperationFailure, ExecutionTimeout):
            return False

        return True

    @reconnect()
    def get(self, key, default=None, version=None):
        coll = self._get_collection()
        key = self.make_key(key, version)
        self.validate_key(key)
        now = timezone.now()

        data = coll.find_one(
            {
                "$and": [
                    {"key": key},
                    {
                        "$or": [
                            {"expires": {"$gt": now}},
                            {"expires": None},
                        ]
                    },
                ]
            }
        )
        if not data:
            return default

        if "data" in data:
            unencoded = base64.decodebytes(data["data"])
            unpickled = pickle.loads(unencoded)
            return unpickled

        return data["data_raw"]

    @reconnect()
    def get_many(self, keys, version=None):
        coll = self._get_collection()
        out = {}
        parsed_keys = {}
        now = timezone.now()

        for key in keys:
            pkey = self.make_key(key, version)
            self.validate_key(pkey)
            parsed_keys[pkey] = key

        data = coll.find(
            {
                "$and": [
                    {"key": {"$in": list(parsed_keys.keys())}},
                    {
                        "$or": [
                            {"expires": {"$gt": now}},
                            {"expires": None},
                        ]
                    },
                ]
            }
        )
        for result in data:
            if "data" in result:
                unencoded = base64.decodebytes(result["data"])
                unpickled = pickle.loads(unencoded)
                out[parsed_keys[result["key"]]] = unpickled
            else:
                out[parsed_keys[result["key"]]] = result["data_raw"]

        return out

    @reconnect()
    def delete(self, key, version=None):
        key = self.make_key(key, version)
        self.validate_key(key)
        coll = self._get_collection()
        if not "capped" in self._db.command("collstats", self._collection_name):
            coll.delete_one({"key": key})
        else:
            coll.update_one({"key": key}, {"$set": {"expires": timezone.now()}})

    @reconnect()
    def has_key(self, key, version=None):
        coll = self._get_collection()
        key = self.make_key(key, version)
        self.validate_key(key)
        now = timezone.now()

        return (
            coll.count_documents(
                {
                    "$and": [
                        {"key": key},
                        {
                            "$or": [
                                {"expires": {"$gt": now}},
                                {"expires": None},
                            ]
                        },
                    ]
                },
                limit=1,
            )
            > 0
        )

    @reconnect()
    def incr(self, key, delta=1, version=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        now = timezone.now()
        coll = self._get_collection()
        key = self.make_key(key, version)
        self.validate_key(key)

        try:
            new_document = coll.find_one_and_update(
                {"key": key},
                {
                    "$inc": {"data_raw": delta},
                    "$set": {"last_change": now},
                },
                return_document=pymongo.ReturnDocument.AFTER,
            )
            if new_document in None:
                raise ValueError("Key %r not found" % key)
            return new_document["data_raw"]
        except (OperationFailure, ExecutionTimeout):
            return False

    @reconnect()
    def ttl(self, key, version=None):
        """
        Get TTL (Time-to-Live) of a key in seconds.
        """
        coll = self._get_collection()
        key = self.make_key(key, version)
        self.validate_key(key)
        now = timezone.now()

        data = coll.find_one(
            {
                "$and": [
                    {"key": key},
                    {"expires": {"$gt": now}},
                ]
            }
        )
        if not data:
            return None

        try:
            return (data["expires"] - now).total_seconds()
        except TypeError:
            return None

    @reconnect()
    def clear(self):
        coll = self._get_collection()
        collstats = self._db.command("collstats", self._collection_name)
        if not "capped" in collstats or not collstats["capped"]:
            coll.delete_many({})
        else:
            coll.update_many({}, {"$set": {"expires": timezone.now()}})

    def _get_collection(self):
        if getattr(self, "_coll", None) is None:
            self._initialize_collection()

        return self._coll

    def _initialize_collection(self):
        self.connection = pymongo.MongoClient(**self._connection_options)
        self._db = self.connection[self._database]
        if self._collection_name not in self._db.list_collection_names():
            options = {}
            if self._max_entries is not None:
                # Create a capped collection
                options.update({"capped": True, "size": self._max_entries})

            self._db.create_collection(self._collection_name, **options)
            collection = self._db[self._collection_name]

            if self.default_timeout is not None:
                # Create a TTL index on "expires" field
                collection.create_index(
                    [
                        ("expires", pymongo.DESCENDING),
                    ],
                    expireAfterSeconds=0,
                )

            # Create an index on "key"/"expires" fields
            collection.create_index(
                [
                    ("key", pymongo.ASCENDING),
                    ("expires", pymongo.ASCENDING),
                ]
            )

        self._coll = self._db[self._collection_name]
