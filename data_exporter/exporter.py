import json
import boto3

def lambda_handler(event, context):
    for sqs_event in event['Records']:

        gen_id = sqs_event.md5_of_body

        item_body = json.loads(sqs_event.body)
        print(gen_id)
