Change log
==========

2024.10.31
--------

* Added support for raw data - all [BSON](https://www.mongodb.com/docs/manual/reference/bson-types/) compatible data stored in Mongo unpickled
* **BREAKING**: Updated `cache.incr(key)` method - only works with raw data ([BSON Types](https://www.mongodb.com/docs/manual/reference/bson-types/))

2023.10.4
--------

* Minimal `pymongo` version bumped to 4.0.2
* Deprecated MongoDB methods updated
* Added support for MongoDB URI
* Added `cache.ttl(key)` method
* Updated `cache.incr(key)` method - does not update `expire` field anymore

2021.7.8
--------

Features unchanged, README was updated.

2021.7.7
----------

* Debugged `clear()` sometimes not working.
* Made the code compatible with python 3.

2018.7.24 (retired release)
---------------------------

* Initial fork
* Use MongoDB's TTL index and capped collections for transparent cache culling