#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import warnings
import traceback
import json
import pprint
import requests

from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory

from zdesk import Zendesk

from OpenSSL import SSL
from twisted.python import log
from twisted.internet.protocol import Protocol, ClientCreator
from twisted.python import usage
from twisted.internet import reactor, ssl, task

from twisted.web.client import Agent
from twisted.internet.ssl import ClientContextFactory
from twisted.web.http_headers import Headers

testconfig = {
	'zdesk_email': 'apachay@octoberry.ru',
	'zdesk_password': 'qDv3q3IxiJWqScVOurhYtaZQaHLDIf5M9quKwY2H',
	'zdesk_url': 'https://smartsupport.zendesk.com',
	'zdesk_token': True
}


#class SmartClientProtocol(WebSocketClientProtocol):
class SmartClientProtocol(WebSocketClientProtocol):
	
	serverPingCall = None
	zdeskPingCall = None
	
	def __init__(self, *args, **kwargs):
		self.serverPingCall = task.LoopingCall(self.doServerPing)
		self.serverPingCall.start(10, 0)
		
		self.zdeskPingCall = task.LoopingCall(self.zdeskNotify)
		self.zdeskPingCall.start(1, 0)

	def __del__(self):
		self.serverPingCall.stop()
		self.zdeskPingCall.stop()

	def doServerPing(self):
		print "Sending PING to Server"
		self.sendMessage("ping")
	
	def onConnect(self, response):
		print("Server connected: {0}".format(response.peer))

	def onOpen(self):
		print("WebSocket connection open.")
		
		
		
		
		print self.sm
		
		"""
		def ping():
			self.sendMessage("ping")
			self.factory.reactor.callLater(10, ping)

		# start sending messages every second ..
		ping()
		"""

	def sayAnswer(self, room=None, message=None):
		answ = { 
					"type" : "message",
					"content" : {
									"room" : room,
									"message" : message,
								}
				}
		answ = json.dumps(answ)
		self.sendMessage(answ)

	def assignTag(self, room=None, tag=None):
		data = { "tag" : tag }
		url = "{0}/api/room/{1}/tags?token={2}".format(self.sm.apiUrl, room, self.sm.serverToken)
		self.sm.POST(url, data, True)

	def zdeskNotify(self):
		room = "55a12b9bb82d04e3b232a99c"
		zendesk = Zendesk(**testconfig)
		results = zendesk.search(query='type:ticket sort:desc', page=1)
		for ticket in results['results']:
			if ticket['status'] == 'solved':
				#send message to ws
				#print "Hey man problem resolved"
				self.sayAnswer(room, "Ваша проблема успешно решена")

				ticket_id = ticket['id']
				data = {
					"ticket": {
						"id": ticket_id,
						"status": "closed"
						}
					}
				response = zendesk.ticket_update(ticket_id, data)
				#self.sayAnswer(room, "ticket %s closed" % ticket_id)
				print "tiket %s closed" % ticket_id



	def onMessage(self, payload, isBinary):
		try:
			msg = payload if isBinary else payload.decode("utf8")
		except:
			traceback.print_exc()

		
		try:
			if msg.lower().strip() == "pong":
				print "Received PONG from Server"
				return

			jmsg = json.loads(msg)
			
			if not jmsg.has_key("type") or not jmsg["type"].strip() == "message":
				return

			pprint.pprint(jmsg)
			
			content = jmsg["content"]
			
			if jmsg.has_key("sender") and jmsg["sender"] == "55a12d30a0b9513ae6d728c1":
				return

			message = content["message"]
			if isinstance(message, list):
				message = " ".join(message)
			
			room = content["room"]
			
			#print self.sm.machAI
			
			for match in self.sm.machAI["match_strings"]:
				n1 = match.strip().lower()
				n2 = message.strip().lower()
				if n1 == n2:
					mr = self.sm.machAI["match_reply"]
					self.sayAnswer(room, mr)
					return

			# not found
			#self.clusterMatchAI
			for match in self.sm.clusterMatchAI["match_strings"]:
				n1 = match.strip().lower()
				n2 = message.strip().lower()
				if n1 == n2:
					if self.sm.clusterMatchAI.has_key("match_reply"):
						mr = self.sm.clusterMatchAI["match_reply"]
						self.sayAnswer(room, mr)
					self.assignTag(room, self.sm.clusterMatchAI["match_tag"])
					return
			

			
		except:
			traceback.print_exc()
			return
		

	def onClose(self, wasClean, code, reason):
		print("WebSocket connection closed: Error: {0}".format(reason))

        

class SmartSupport(object):

	baseHost = None
	apiSchema = "https://"
	wsSchema = "wss://"
	apiUrl = None
	wsUrl = None
	apiUser = None

	timeout = None
	machAI = {}
	clusterMatchAI = {}
	
	serverToken = None
	
	def __init__(self):
		pass

	def __close__(self):
		pass

	def setBaseHost(self, host=None):
		self.baseHost = host

	def setApiSchema(self, apiSchema=None):
		self.apiSchema = apiSchema

	def setWebSocketSchema(self, wsSchema=None):
		self.wsSchema = wsSchema
	
	def setTimeout(self, t=None):
		self.timeout = t

	def buildApiUrl(self):
		return "{0}{1}".format(self.apiSchema, self.baseHost)
		
	def buildWebSocketUrl(self):
		return "{0}{1}/relay".format(self.wsSchema, self.baseHost)

	def setApiAuth(self, user, pwd):
		self.setApiAuth = (user, pwd)

	def initMachineLearningFile(self, f):
		self.machAI = {}
		try:
			self.machAI = json.loads(open(f, "rb").read())
			print "AI was loaded!"
		except Exception, ex:
			print "AI wasn't loaded. Error: {0}".format(ex.message)

	def initClusterMachineLearningFile(self, f):
		self.clusterMatchAI = {}
		try:
			self.clusterMatchAI = json.loads(open(f, "rb").read())
			print "Cluster AI was loaded!"
		except Exception, ex:
			print "Cluster AI wasn't loaded. Error: {0}".format(ex.message)
	

	def startLogging(self):
		log.startLogging(sys.stdout)

	def display(response):
		print "Received response"
		print response

	def POST(self, url=None, data={}, ignoreOutput=False):
		try:
			r = requests.post(url=url, data=data, timeout=self.timeout, verify=False)
			if ignoreOutput:
				return
			return json.loads(r.text)
		except:
			traceback.print_exc()
			return {}
		
	def GET(self, url=None, data={}, ignoreOutput=False):
		try:
			r = requests.get(url=url, data=data, timeout=self.timeout, verify=False)
			if ignoreOutput:
				return
			return json.loads(r.text)
		except:
			return {}



	def startDaemon(self):
		
		# build urls
		self.apiUrl = self.buildApiUrl()
		self.wsUrl = self.buildWebSocketUrl()
		
		# get token
		data = { "login" : self.setApiAuth[0], "password" : self.setApiAuth[1] }
		url = "{0}/api/auth".format(self.apiUrl)
		r = self.POST(url, data)
		
		self.serverToken = r["token"]
		
		factory = WebSocketClientFactory(self.buildWebSocketUrl() + "?token={0}".format(self.serverToken), debug=False)
		factory.protocol = SmartClientProtocol
		factory.protocol.sm = self
		reactor.connectSSL(self.baseHost, 443, factory, ssl.ClientContextFactory())
		

sm = SmartSupport()
sm.startLogging()
sm.setBaseHost("my-dev.allychat.ru")
sm.setApiSchema("https://")
sm.setWebSocketSchema("wss://")
sm.setTimeout(5)
sm.setApiAuth("admin", "1vFamm")
sm.initMachineLearningFile("matches.json")
sm.initClusterMachineLearningFile("cluster_matches.json")
sm.startDaemon()

reactor.run()

