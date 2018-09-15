from sqlalchemy import inspect, or_, and_
from sqlalchemy import create_engine, MetaData, Table, Column, ForeignKey
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker, collections, scoped_session
from sqlalchemy.ext.declarative import DeclarativeMeta
from decimal import Decimal
import datetime
import json
import time
import uuid

#Predefined variables that in the future will not be hardcoded
s3_bucket =  os.environ.get("S3_BUCKET", "pat-etl-testing")
db_type = "mssql"
db_library = "pymssql"
db_username = "sa"
db_password = "NewYearNewMe9"
db_location = "localhost"
db_port = "1433"
db_name = "AdventureWorks2017"
schema = "Person"

metadata = MetaData()
if schema is not None:
    metadata.schema = schema
#create connection string works for most SQL dbs
connection_str = "{0}+{1}://{2}:{3}@{4}:{5}/{6}".format(db_type, db_library, db_username,
                                                       db_password, db_location, db_port, db_name)
#create engine the connection to the databse
engine = create_engine(connection_str)
engine.connect()

metadata.reflect(bind=engine, views=True)
#Create base that grabs all the database automapped info; gets database structure
Base = automap_base(metadata=metadata)
Base.prepare()
#Create session maker
Session = scoped_session(sessionmaker(bind=engine))
#create session instance
session = Session()

#Query SQL based on a list of filters
def _sql_query(filter_list, table):
    filter_group = []
    for filter_item in filter_list:
        #if filter type is equal then apply the == filter
        if filter_item["type"] == "eq":
            filter_group.append(getattr(table, filter_item["field"]) == filter_item["value"])
        elif filter_item["type"] == "le":
            filter_group.append(getattr(table, filter_item["field"]) <= filter_item["value"])
        elif filter_item["type"] == "ge":
            filter_group.append(getattr(table, filter_item["field"]) >= filter_item["value"])
    #Finally query table with the collective filters and get all items
    return session.query(table).filter(and_(*filter_group)).all()

#This function flattens related tables into a dictionary object
#Pass in an intial dictionary usually empty, then a dont_include array of fields to not include
#And finally the sql alchemy item
def _expand_to_dict(initial_dict, dont_include, item):
    #ignore all the sql alchemy fields that are defaulted
    to_expand = [x for x in dir(item) if not x.startswith("_") and x != "metadata"]
    for field in to_expand:
        #Get field from sqlalchemy item dynamically using getattr
        val =  getattr(item, field)
        #Ignore empty fields and Sometimes relations can be circular so add some fields to dont include 
        if val == None or field in dont_include:
            continue
        #if val is a dictionary then need to recursively call and create nested dict
        if isinstance(val.__class__, DeclarativeMeta) and val.__class__ in dont_include:
            dont_include.append(val.__class__)
            initial_dict[field] = {}
            initial_dict[field] = _expand_to_dict(initial_dict[field], dont_include, val)
        #If val is a list of sqlalchemy classes then loop through and recursively created those dicts
        elif (isinstance(val, list) and len(val) > 0 and isinstance(val[0].__class__, DeclarativeMeta)):
            if field in dont_include:
                continue
            #create array for nested items
            initial_dict[field] = []
            for idx, subitem in enumerate(val):
                initial_dict[field].append({})
                initial_dict[field][idx] = _expand_to_dict(initial_dict[field][idx], dont_include, val[idx])
                
        elif isinstance(val.__class__, DeclarativeMeta):
            continue
        #If standard value just set it in dict
        else:
            initial_dict[field] = val
    return initial_dict

class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%dT%H:%M:%S.%Z")
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        else:
            return super(MyEncoder, self).default(obj)

def _data_generator(sql_items):
    for item in sql_items:
        sql_dict = _expand_to_dict({}, ['classes', 'prepare'], item)
        yield json.dumps(sql_dict, cls=MyEncoder) + "\n"

def _create_s3_key(date):
    key_str = "{0}/{1}/{2}/data_{3}.gz".format(date.strftime('%Y'), date.strftime('%m'),
                        date.strftime('%d'), date.strftime('%H-%M-%S'))
    return key_str

def main_handler():
    filter_list = []
    table = getattr(Base.classes, "Person")
    sql_items = _sql_query(filter_list, table)
    gen_data =  _data_generator(sql_items)
    with io.BytesIO() as outfile:
        for chunk in gen_data:
            outfile.write(chunk)
        current_date = datetime.datetime.now()

        s3_key = _create_s3_key(current_date)
        s3_object = s3.Object(s3_bucket, s3_key)
        s3_object.put(Body=gzip.compress(outfile))

if __name__ == "__main__":
    main()