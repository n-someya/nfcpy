.. _snep-tutorial:
.. currentmodule:: nfc.snep

*****************************
Simple NDEF Exchange Protocol
*****************************

The NFC Forum Simple NDEF Exchange Protocol (SNEP) allows two NFC
devices to exchange NDEF Messages. It is implemented in many
smartphones and typically used to push phonebook contacts or web page
URLs to another phone.

SNEP is a stateless request/response protocol. The client sends a
request to the server, the server processes that request and returns a
response. On the protocol level both the request and response have no
consequences for further request/response exchanges. Information units
transmitted through SNEP are NDEF messages. The client may use a SNEP
PUT request to send an NDEF message and a SNEP GET request to retrieve
an NDEF message. The message to retrieve with a GET request depends on
an NDEF message sent with the GET request but the rules to determine
equivalence are an application layer contract and not specified by
SNEP.

NDEF messages can easily be larger than the maximum information unit
(MIU) supported by the LLCP data link connection that a SNEP client
establishes with a SNEP server. The SNEP layer handles fragmentation
and reassembly so that an application must not be concerned. To avoid
exhaustion of the limited NFC bandwidth if an NDEF message would
exceed the SNEP receiver's capabilities, the receiver must acknowledge
the first fragment of an NDEF message that can not be transmitted in a
single MIU. The acknowledge can be either the request/response codes
CONTINUE or REJECT. If CONTINUE is received, the SNEP sender shall
transmit all further fragments without further acknowledgement (the
LLCP data link connection guarantees successful transmission). If
REJECT isreceived, the SNEP sender shall abort
tranmsission. Fragmentation and reassembly are handled transparently
by the :class:`nfc.snep.SnepClient` and :class:`nfc.snep.SnepServer`
implementation and only a REJECT would be visible to the user.

A SNEP server may return other response codes depending on the
result of a request:

* A "Success" response indicates that the request has succeeded. For a
  Get request the response will include an NDEF message. For a PUT
  request the response is empty.
* A "Not Found" response says that the server has not found anything
  matching the request. This may be a temporary of permanent
  situation, i.e. the same request send later could yield a different
  response.
* An "Excess Data" response may be received if the server has found a
  matching response but sending it would exhaust the SNEP client's
  receive capabilities.
* A "Bad Request" response indicates that the server detected a syntax
  error in the client's request. This should almost never be seen.
* The "Not Implemented" response will be returned if the client sent a
  request that the server has not implemented. It applies to existing
  as well as yet undefined (future) request codes. The client can
  learn the difference from the version field transmitted withnthe
  response, but in reality it doesn't matter - it's just not
  supported.
* With "Unsupported Version" the server reacts to a SNEP request that
  has a version number it doesn't support or refuses to support. This
  should be seen only if the client sends with a higher major version
  number than the server has implemented. It could be received also if
  the client sends with a lower major version number but SNEP servers
  are likely to support historic major versions if that ever happens
  (the current SNEP version is 1.0).

Besides the protocol layer the SNEP specification also defines a
*Default SNEP Server* with the well-known LLCP service access point
address 4 and service name `urn:nfc:sn:snep`. Certified NFC Forum
Devices must have the *Default SNEP Server* implemented. Due to that
requirement the feature set and guarantees of the *Default SNEP
Server* are quite limited - it only implements the PUT request and the
NDEF message to put could be rejected if it is more than 1024 octets,
though smartphones generally seem to support more.

Running a Default Server
------------------------

A *Default SNEP Server* can be set-up by instantiating and customizing
a :class:`nfc.snep.SnepServer`. The following example shows the
standard pattern of initializing a server component during the
preparation phase and starting it when a remote device has
connected. The *put_records* function is set as a callback for
handling SNEP Put request messages with an information field of up to
1000 octets NDEF message data. SNEP Get requests are automatically
rejected with a "Not Implemented" response.

.. note:: The examples make use of the ``udp`` driver that allows two
   *nfcpy* stacks to connect without physical contactless frontend
   hardware. This is used to automatically test the example code when
   the docuemntation is built. The code to test drive an example can
   be seen in the source code of the documentation.

.. testsetup:: default_server

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
           nfc.snep.SnepClient(llc).put_records([ndef.TextRecord('Hello World')])

   PeerDevice().start()

.. testcode:: default_server

   import nfc
   import ndef

   def put_records(request_records):
       for record in request_records:
           print(record)

   def on_startup(llc):
       snep_server = nfc.snep.SnepServer(llc, acceptable_length=1024)
       snep_server.set_callback(put_records=put_records)
       llc.private.snep_server = snep_server
       return llc

   def on_connect(llc):
       llc.private.snep_server.start()
       return True

   clf = nfc.ContactlessFrontend('udp::54321')
   clf.connect(llcp={'on-startup': on_startup, 'on-connect': on_connect})

.. testoutput:: default_server
   :hide:

   NDEF Text Record ID '' Text 'Hello World' Language 'en' Encoding 'UTF-8'


Sending an NDEF message
-----------------------

Support for sending SNEP Get or Put requests is implemented by the
:class:`nfc.snep.SnepClient` class. To send (Put) an NDEF message to
the *Default SNEP Server* use :meth:`~nfc.snep.SnepClient.put_records`
with the list of NDEF Records to transmit, as shown in the following
example. Note that the actual sending must be deferred to a separate
thread because the ``on_connect`` callback has to return immediately
for the link control protocol to start the protocol data unit
exchange.

.. note:: Some phones default to always connect to the peer's *Default
   SNEP Server* even if they are not going to send anything (Windows
   Phone 8 is one example). For that reason the example code also
   initializes and starts a *Default SNEP Server* which, not being
   customized, will simply trash any SNEP Put request and respond
   "Success".

.. testsetup:: put_records

   import nfc, ndef, threading, time

   class PeerDevice(threading.Thread):
       def put_records(self, request_records):
           for record in request_records:
               print(record)

       def on_startup(self, llc):
           llc.private.snep_server = nfc.snep.SnepServer(llc, put_records=self.put_records)
           return llc

       def on_connect(self, llc):
           llc.private.snep_server.start()
           return True

       def run(self):
           started = time.time()
           terminate = lambda: (time.time() - started) > 0.1
           clf = nfc.ContactlessFrontend('udp::54322')
           clf.connect(llcp={'on-startup': self.on_startup, 'on-connect': self.on_connect}, terminate=terminate)

   PeerDevice().start()

.. testcode:: put_records

   import nfc
   import ndef
   from threading import Thread

   def send_ndef_message(llc):
       records = [ndef.SmartposterRecord('http://nfcpy.org', title='nfcpy home')]
       nfc.snep.SnepClient(llc).put_records(records)

   def on_connect(llc):
       Thread(target=send_ndef_message, args=(llc,)).start()
       llc.private.snep_server.start()
       return True

   def on_startup(llc):
       llc.private.snep_server = nfc.snep.SnepServer(llc)
       return llc

   clf = nfc.ContactlessFrontend("udp::54322")
   clf.connect(llcp={'on-startup': on_startup, 'on-connect': on_connect})

.. testoutput:: put_records
   :hide:

   NDEF Smartposter Record ID '' Resource 'http://nfcpy.org' Title 'nfcpy home'


Private Servers
---------------

The SNEP protocol can be used for communication between other server
and client applications that agree on the syntax and semantics of the
information exchanged with the SNEP Get and Put requests. The only
requirement is that they do not use the well-know service name
``urn:nfc:sn:snep`` that is reserved for the *Default SNEP Server*.

The following example implements a simple NDEF message store where the
type of the first NDEF record serves as the key under which the NDEF
message is stored and and can be retrieved. The server registers with
an external service name as ``ndef-store`` under the ``nfcpy.org``
domain. The example also demonstrates how a SNEP error responses is
generated by raising :exc:`~nfc.snep.SnepError`.

.. testsetup:: ndef_store_server

   import nfc, ndef, threading, time

   class PeerDevice(threading.Thread):
       def run(self):
           started = time.time()
           terminate = lambda: (time.time() - started) > 0.1
           clf = nfc.ContactlessFrontend('udp::54323')
           clf.connect(llcp={'on-connect': self.on_connect}, terminate=terminate)

       def on_connect(self, llc):
           threading.Thread(target=self.snep_records, args=(llc,)).start()
           return True

       def snep_records(self, llc):
           with nfc.snep.SnepClient(llc, "urn:nfc:xsn:nfcpy.org:ndef-store") as snep_client:
               snep_client.put_records([ndef.TextRecord('Hello World')])
               print(snep_client.get_records([ndef.TextRecord('')]))

   PeerDevice().start()

.. testcode:: ndef_store_server

   import nfc
   import ndef

   ndef_storage = {}

   def put_records(request_records):
       if len(request_records) > 0:
           key = request_records[0].type
           ndef_storage[key] = request_records

   def get_records(request_records):
       try:
           return ndef_storage[request_records[0].type]
       except KeyError:
           raise nfc.snep.SnepError(nfc.snep.NotFound)
       except IndexError:
           raise nfc.snep.SnepError(nfc.snep.BadRequest)

   def on_startup(llc):
       snep_server = nfc.snep.SnepServer(llc, service_name="urn:nfc:xsn:nfcpy.org:ndef-store")
       snep_server.set_callback(get_records=get_records, put_records=put_records)
       llc.private.snep_server = snep_server
       return llc

   def on_connect(llc):
       llc.private.snep_server.start()
       return True

   clf = nfc.ContactlessFrontend('udp::54323')
   clf.connect(llcp={'on-startup': on_startup, 'on-connect': on_connect})

.. testoutput:: ndef_store_server
   :hide:

   [ndef.text.TextRecord(u'Hello World', 'en', 'UTF-8')]


A corresponding client application for the NDEF storage server is
shown below. Here the client first connects to the NDEF storage server
then puts an NDEF text message into the store and retrieves it
back. The following get request then tries to retrieve an NDEF URI
Record for which the server replies "Not Found".

.. testsetup:: ndef_store_client

   import nfc, ndef, threading, time

   class PeerDevice(threading.Thread):
       ndef_storage = {}

       def put_records(self, request_records):
           if len(request_records) > 0:
               self.ndef_storage[request_records[0].type] = request_records

       def get_records(self, request_records):
           try:
               return self.ndef_storage[request_records[0].type]
           except KeyError:
               raise nfc.snep.SnepError(nfc.snep.NotFound)
           except IndexError:
               raise nfc.snep.SnepError(nfc.snep.BadRequest)

       def on_startup(self, llc):
           llc.private.snep_server = nfc.snep.SnepServer(llc, service_name="urn:nfc:xsn:nfcpy.org:ndef-store")
           llc.private.snep_server.set_callback(get_records=self.get_records, put_records=self.put_records)
           return llc

       def on_connect(self, llc):
           llc.private.snep_server.start()
           return True

       def run(self):
           started = time.time()
           terminate = lambda: (time.time() - started) > 0.1
           clf = nfc.ContactlessFrontend('udp::54324')
           clf.connect(llcp={'on-startup': self.on_startup, 'on-connect': self.on_connect}, terminate=terminate)

   PeerDevice().start()

.. testcode:: ndef_store_client

   import nfc
   import ndef

   def main(llc):
       client = nfc.snep.SnepClient(llc)
       client.connect("urn:nfc:xsn:nfcpy.org:ndef-store")
       try:
           client.put_records([ndef.TextRecord('Hello World')])
           print(client.get_records([ndef.TextRecord('')]))
           client.get_records([ndef.UriRecord('')])
       except nfc.snep.SnepError as error:
           print(error)
       finally:
           client.close()

   def on_connect(llc):
       threading.Thread(target=main, args=(llc,)).start()
       return True

   clf = nfc.ContactlessFrontend('udp::54324')
   clf.connect(llcp={'on-connect': on_connect})

.. testoutput:: ndef_store_client

   [ndef.text.TextRecord(u'Hello World', 'en', 'UTF-8')]
   nfc.snep.SnepError: [192] resource not found

