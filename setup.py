from setuptools import setup, find_packages

setup(
    name='django-cache-with-mongodb',
    version='2018.07.24',
    packages=['django_cache_with_mongodb'],
    package_dir={'django_cache_with_mongodb': 'django_cache_with_mongodb'},
    provides=['django_cache_with_mongodb'],
    include_package_data=True,
    url='https://github.com/Olivier-OH/django_cache_with_mongodb',
    license=open('LICENSE').read(),
    author='Olivier Hoareau',
    author_email='olivier.p.hoareau@gmail.com',
    maintainer='Olivier Hoareau',
    maintainer_email='olivier.p.hoareau@gmail.com',
    description='Provides caching ability through MongoDB. Forked and detached from django_mongodb_cash_backend.',
    long_description=open('README.md').read(),
    install_requires=[
        'pymongo==3.*'
    ],
    keywords=[
        'django',
        'web',
        'cache',
        'mongodb'
    ],
    platforms='OS Independent',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Framework :: Django',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development'
    ],
)
