import os
import queue
import concurrent_sqs 
import json
import boto3
import gzip
import io

#Get a list of sqs queues to send data too, might be mulitple if
#we need to split the data
sqs_queues =  os.environ.get("SQS_QUEUES", ["json-lines-test"])
#Fields to remove if dont want in end source
fields_to_remove =  os.environ.get("REMOVE_FIELDS", None)

#declare s3 resource, and set session, will probably change in future because this isnt generic just for testign
s3 = boto3.resource('s3')
# boto3.setup_default_session(profile_name='personal')

#loadss a pickled model from s3 to possibly use for tagging or splitting
def _load_model(bucket_name, model_key):
    return pickle.load(io.BytesIO(s3.get_object(Bucket=bucket_name, Key=model_key)['Body'].read()))

#read file as stream, unzip file and buffer based on newlines
#yield one row at a time to save memory
def _read_file(file_):
    with gzip.GzipFile(fileobj=file_, mode="r") as gzf:
        with io.TextIOWrapper(gzf, encoding="utf8", line_buffering=True) as txt_wrapper:
            for row in txt_wrapper:
                yield row

#removes fields in data dict 
def _remove_fields(data_dict, entities_to_remove):
    values_removed = [data_dict.pop(k, None) for k in entities_to_remove]
    return data_dict

#IMPLEMENT IF need files split, default just return 1st queue
def _split_files(dict_obj):
    return sqs_queues[0]

def main_handler(s3_bucket, s3_key):
    #create python queue to handle multithreaded aws sqs io
    #create a deictionary of senders and batches, a new thread for each possible sqs split
    sqs_senders = {}
    batches = {}
    for sqs_queue_name in sqs_queues:
        #create sqs sender
        pat_queue = queue.Queue()
        sqs_sender = concurrent_sqs.sqs_handler(pat_queue, sqs_queue_name)
        #start the sqs thread as a daemon
        sqs_sender.setDaemon(True)
        sqs_sender.start()
        #add sender to dict of possible split senders
        sqs_senders[sqs_queue_name] = pat_queue
        batches[sqs_queue_name] = []


    #read in json lines file and create an iterable generator
    response = s3.Object(bucket_name=s3_bucket, key=s3_key)
    json_lines = _read_file(response.get()["Body"]._raw_stream)

    for json_obj in json_lines:
        #load in a json obj one line at a time
        temp_obj = json.loads(json_obj)
        #possibly remove fields if need too
        if fields_to_remove:
            temp_obj = _remove_fields(temp_obj, fields_to_remove)
        #choose queue to send to 
        chosen_queue = _split_files(temp_obj)
        #append that object to a list
        batches[sqs_queue_name].append(temp_obj)
        #batch send the records when 10 are reached
        if len(batches[sqs_queue_name]) % 10 == 0:
            #put records in queue
            sqs_senders[sqs_queue_name].put(batches[sqs_queue_name])
            batches[sqs_queue_name] = []
    #if there are batches unsent send them
    for unsent_batch in batches:
        if unsent_batch:
            sqs_senders[sqs_queue_name].put(batches[sqs_queue_name])
    # wait for the queue to finish
    for queue_key in sqs_senders:
        sqs_senders[sqs_queue_name].join()
 
def lambda_handler(event, context):
    for s3_event in event['Records']:
        print(s3_event)
        key = s3_event['s3']['object']['key']
        bucket = s3_event['s3']['bucket']['name']
        main_handler(bucket, key)

