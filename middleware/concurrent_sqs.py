import threading
import boto3
import json
#temp to set session will change after testing
# boto3.setup_default_session(profile_name='personal')

class sqs_handler(threading.Thread):
 
    def __init__(self, queue, sqs_queue_name):
        threading.Thread.__init__(self)
        #Set queue to read from
        self.queue = queue
        #get sqs by name
        sqs = boto3.resource('sqs')
        self.sqs_queue = sqs.get_queue_by_name(QueueName=sqs_queue_name)
    #----------------------------------------------------------------------
    def run(self):
        #run forever until queue.join is called and queue is empty
        while True:
            # gets array of dicts from concurrent queue
            messages = self.queue.get()

            #format entries to send to sqs
            entries = self._format_sqs(messages)
            #send batch of entries to sqs
            response = self.sqs_queue.send_messages(Entries=entries)
            #Need to add error handling, right now just print failed records
            print(response.get('Failed'))
            #Set task to done
            self.queue.task_done()

    #Format sqs messages, create unique batch id and string messagebody
    def _format_sqs(self, messages):
        entries = [{"Id" : str(idx), "MessageBody" : json.dumps(message)} for idx, message in enumerate(messages)]
        return entries