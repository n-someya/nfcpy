nfc.snep
========

.. automodule:: nfc.snep

nfc.snep.SnepClient
-------------------

.. autoclass:: SnepClient
   :members:

nfc.snep.SnepServer
-------------------

The :class:`SnepServer` implemements protocol handling for the Simple
NDEF Exchange Protocol (SNEP) Get and Put messages.  An application
must set callbacks for *get_records* or *get_octets* and *put_records*
or *put_octets* to customize it's behavior. The default implementation
returns the SNEP "Not Implemented" response for Get requests and the
SNEP "Success" response for Put requests. A SNEP Server instance must
be created before and started during LLCP link establishment by the
application.

.. testsetup:: records

   import nfc, ndef, threading, time
   class PeerDevice(threading.Thread):
       def run(self):
           started = time.time()
           terminate = lambda: (time.time() - started) > 0.1
           clf = nfc.ContactlessFrontend('udp::54321')
           clf.connect(llcp={'on-connect': self.on_connect}, terminate=terminate)
       def on_connect(self, llc):
           threading.Thread(target=self.snep_records, args=(llc,)).start()
           return True
       def snep_records(self, llc):
           with nfc.snep.SnepClient(llc) as snep_client:
               snep_client.put_records([ndef.TextRecord('Hello World')])
               request_records = [ndef.Record('unknown', 'temperature')]
               assert snep_client.get_records(request_records) == [ndef.TextRecord('25.1')]
               try: snep_client.get_records([ndef.Record('unknown', 'humidity')])
               except nfc.snep.SnepError as e: assert e.errno == nfc.snep.NotFound
               else: assert False, "DID NOT RAISE"
   PeerDevice().start()

.. testcode:: records

   import nfc
   import ndef

   def put_records(request_records):
       for record in request_records:
           print(record)

   def get_records(request_records):
       if request_records and request_records[0].name == b'temperature':
           return [ndef.TextRecord('25.1')]
       else:
           raise nfc.snep.SnepError(nfc.snep.NotFound)

   def on_startup(llc):
       snep_server = nfc.snep.SnepServer(llc)
       snep_server.set_callback(put_records=put_records)
       snep_server.set_callback(get_records=get_records)
       llc.private.snep_server = snep_server
       return llc

   def on_connect(llc):
       llc.private.snep_server.start()
       return True

   clf = nfc.ContactlessFrontend('udp::54321')
   clf.connect(llcp={'on-startup': on_startup, 'on-connect': on_connect})

.. testoutput:: records
   :hide:

   NDEF Text Record ID '' Text 'Hello World' Language 'en' Encoding 'UTF-8'

More control over the generated response data and processing of
request data can be achieved with the *get_octets* and *put_octets*
callback functions. For example, the *get_octets* callback receives an
additional argument that indicates the maximum number of response data
octets which the client is able to process. This may allow an advanced
server implementation to return a shorter version of the requested
information to a limited client.

.. testsetup:: with_octets

   import nfc, ndef, threading, time
   class PeerDevice(threading.Thread):
       def run(self):
           self.started = time.time()
           self.terminate = lambda: (time.time() - self.started) > 0.1
           clf = nfc.ContactlessFrontend('udp::54322')
           clf.connect(llcp={'on-connect': self.on_connect}, terminate=self.terminate)
       def on_connect(self, llc):
           threading.Thread(target=self.snep_request, args=(llc,)).start()
           return True
       def snep_request(self, llc):
           with nfc.snep.SnepClient(llc) as snep_client:
               snep_client.put_records([ndef.TextRecord('Hello World')])
               request_records = [ndef.Record('unknown', 'temperature')]
               assert snep_client.get_records(request_records) == [ndef.TextRecord('Temperature is 25.1 degree')]
               assert snep_client.get_records(request_records, 16) == [ndef.TextRecord('25.1')]
               try: snep_client.get_records([ndef.Record('unknown', 'humidity')])
               except nfc.snep.SnepError as e: assert e.errno == nfc.snep.NotFound
               else: assert False, "DID NOT RAISE"
   PeerDevice().start()


.. testcode:: with_octets

   def get_octets(request_octets, acceptable_length):
       request_records = list(ndef.message_decoder(request_octets))
       if request_records and request_records[0].name == 'temperature':
           text = '25.1' if acceptable_length <= 16 else 'Temperature is 25.1 degree'
           return b''.join(ndef.message_encoder([ndef.TextRecord(text)]))
       raise nfc.snep.SnepError(0xC0)  # Not Found

   def put_octets(request_octets):
       for record in ndef.message_decoder(request_octets):
           print(record)

   def on_startup(llc):
       snep_server = nfc.snep.SnepServer(llc)
       snep_server.set_callback(put_octets=put_octets)
       snep_server.set_callback(get_octets=get_octets)
       llc.private.snep_server = snep_server
       return llc

   def on_connect(llc):
       llc.private.snep_server.start()
       return True

   clf = nfc.ContactlessFrontend('udp::54322')
   clf.connect(llcp={'on-startup': on_startup, 'on-connect': on_connect})

.. testoutput:: with_octets
   :hide:

   NDEF Text Record ID '' Text 'Hello World' Language 'en' Encoding 'UTF-8'

.. autoclass:: SnepServer
   :members:

.. autoclass:: SnepError
   :members:
