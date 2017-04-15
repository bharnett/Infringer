#!/usr/bin/python
####################################################################################
##                                  INFORMATION
####################################################################################
##   Developed by: Steven Johnson
##
##   Last Updated: 11/13/2013 4:00AM PST
##   
##   Description: Auto-Delete Watched Items In Plex
##
##   Required Configurations:
##      - PC       (Blank = AutoDetect  |  W = Windows  |  L = Linux/Unix/MAC )
##      - Host     (Hostname or IP  | Blank = 127.0.0.1)
##      - Port     (Port  |  Blank = 32400)
##      - Section  (Section aka Library 1 2 3 varies on your system  |  Blank = 1)
##      - Delete   (1 = Delete  |  Blank = 0 (For Testing or Review))
##      - Shows    ( ["Show1","Show2"]; = Kept Shows OR [""]; = DEL ALL SHOWS )
##      - OnDeck   ( 1 = Keep If On Deck  |  Blank = Delete Regardless if onDeck  )
##
####################################################################################
####################################################################################

PC = "L";
Host = "";
Port = "";
Section = "1";
Delete = "1";
Shows = ["The Simpsons"];
OnDeck = "1";
Movie_Section = "2"
NetworkMoviePath = "/Volumes/public/movies/"

####################################################################################
##                        NO NEED TO EDIT BELOW THIS LINE  
####################################################################################
import os
import xml.dom.minidom
import platform
import re
import requests
import shutil
####################################################################################
##  Checking URL
####################################################################################
if Host=="":
  Host="127.0.0.1"
if Port=="":
  Port="32400"
if Section=="":
  Section = "1"
URL = ("http://" + Host + ":" + Port + "/library/sections/" + Section + "/folder")
OnDeckURL = ("http://" + Host + ":" + Port + "/library/sections/" + Section + "/onDeck")
Movie_Url = ("http://" + Host + ":" + Port + "/library/sections/" + Movie_Section + "/rating/10")
print("")
print("                           Detected Settings")
print("")
print("Host: " + Host)
print("Port: " + Port)
print("Section: " + Section)
print("URL: " + URL)
print("OnDeck URL: " + OnDeckURL)

####################################################################################
##  Get Auth Tokens
####################################################################################
plex_unique_id = '8cab94b9-f1e1-41b6-8c02-69ff9e886e1b'
plex_client_name = 'PlexDeleteWatched'
plex_version = '1.0.0.0'
plex_user_token = ''
plex_server_token = ''
plex_username = 'bharnett1825@gmail.com'
plex_pw = 'plexytime'
plex_auth_url = 'https://plex.tv/users/sign_in.json'
plex_servers_url = 'https://plex.tv/pms/servers.xml'
plex_server_name = "brian's Mac mini"

payload = {'user[password]': plex_pw, 'user[login]': plex_username}
headers = {'X-Plex-Product': plex_unique_id, 'X-Plex-Client-Identifier' : plex_client_name, 'X-Plex-Version' : plex_version}
r = requests.post(plex_auth_url, params=payload, headers=headers)
response_json = r.json()
plex_user_token = response_json['user']['authToken']
server_request = requests.get(plex_servers_url, headers={'X-Plex-Token': plex_user_token})
server_response = xml.dom.minidom.parseString(server_request.text)
servers = xml.dom.minidom.parseString(server_request.text).getElementsByTagName('Server')

if len(servers) == 0:
    print('No server token found with matching plex server name %s.' % plex_server_name )
    exit()


for server in servers:
    if server.getAttribute('name') == plex_server_name:
        plex_server_token = server.getAttribute('accessToken')

if plex_server_token == '':
    plex_server_token = servers[0].getAttribute('accessToken')  # get first if you can't find a match

####################################################################################
##  Checking Shows
####################################################################################
NoDelete = " | "
ShowCount = len(Shows)
print("Show Count: " + str(ShowCount))

for Show in Shows:
  Show = re.sub('[^A-Za-z0-9 ]+', '', Show).strip()
  if Show=="":
    NoDelete += "(None Listed) | "
    ShowCount -= 1
  else:
    NoDelete += Show + " | "

print("Number of Shows Detected For Keeping: " + str(ShowCount))
print ("Shows to Keep:" + NoDelete)

###################################################################################
##  Checking Delete
####################################################################################
if Delete=="1":
  print("Delete: ***Enabled***")
else:
  print("Delete: Disabled - Flagging Only")

if OnDeck=="1":
  print("Delete OnDeck: No")
else:
  print("Delete OnDeck: Yes")

####################################################################################
##  Checking OS
####################################################################################
AD = ""
if PC=="":
  AD = "(Auto Detected)"
  if platform.system()=="Windows":
    PC = "W"
  elif platform.system()=="Linux":
    PC = "L"
  elif platform.system()=="Darwin":
    PC = "L"

####################################################################################
##  Setting OS Based Variables
# ####################################################################################
# if PC=="L":
#   print("Operating System: Linux " + AD)
#from urllib.request import urlopen
doc = xml.dom.minidom.parseString(requests.get(URL, headers={'X-Plex-Token': plex_server_token}).text)
deck = xml.dom.minidom.parseString(requests.get(OnDeckURL, headers={'X-Plex-Token': plex_server_token}).text)
movie_doc = xml.dom.minidom.parseString(requests.get(Movie_Url, headers={'X-Plex-Token': plex_server_token}).text)

  #doc = xml.dom.minidom.parse(urlopen(URL))
  #deck = xml.dom.minidom.parse(urlopen(OnDeckURL))
# elif PC=="W":
#   print("Operating System: Windows " + AD)
#   import urllib.request
#   doc = xml.dom.minidom.parse(urllib.request.urlopen(URL))
#   deck = xml.dom.minidom.parse(urllib.request.urlopen(OnDeckURL))
# else:
#   print("Operating System: ** Not Configured **  (" + platform.system() + ") is not recognized.")
#   exit()
# print("")
# print("")
# print("")


FileCount = 0
DeleteCount = 0
FlaggedCount = 0
OnDeckCount = 0
ShowsCount = 0

####################################################################################
##  Check On Deck
####################################################################################
def CheckOnDeck( CheckDeckFile ):
  InTheDeck = 0
  for DeckVideoNode in deck.getElementsByTagName("Video"):
    DeckMediaNode = DeckVideoNode.getElementsByTagName("Media")
    for DeckMedia in DeckMediaNode:
      DeckPartNode = DeckMedia.getElementsByTagName("Part")
      for DeckPart in DeckPartNode:
        Deckfile = DeckPart.getAttribute("file")
        if CheckDeckFile==Deckfile:
          InTheDeck += 1
        else:
          InTheDeck += 0
  return InTheDeck
 
####################################################################################
##  Check Shows And Delete If Configured
####################################################################################
def CheckShows( CheckFile ):
  global FileCount
  global DeleteCount
  global FlaggedCount
  global OnDeckCount
  global ShowsCount
  FileCount += 1
  CantDelete = 0
  ShowFound = ""
 
##  -- CHECK SHOWS --  
  for Show in Shows:
    Show = re.sub('[^A-Za-z0-9 ]+', '', Show).strip()
    if Show=="":
      CantDelete = 0
    else:
      if (' ' in Show) == True:
        if all(str(Word) in CheckFile for Word in Show.split()):
          CantDelete += 1
          ShowFound = "[" + Show + "]"
          ShowsCount += 1
        else:
          CantDelete += 0
      else:
        if Show in CheckFile:
          CantDelete += 1
          ShowFound = "[" + Show + "]"
          ShowsCount += 1
        else:
          CantDelete += 0

## -- Check OnDeck --
  if OnDeck=="1":
    IsOnDeck = CheckOnDeck(CheckFile);
    if IsOnDeck==0:
      CantDelete += 0
    else:
      CantDelete += 1
      ShowFound = "[OnDeck]" + ShowFound
      OnDeckCount += 1

## -- DELETE SHOWS --
  if CantDelete == 0:
    if Delete=="1":
      print("**[DELETED] " + CheckFile)
      os.remove(file)
      DeleteCount += 1
    else:
      print("**[FLAGGED] " + CheckFile)
      FlaggedCount += 1
  else:
    #print ("[KEEPING] %s ' ' %s") % (ShowFound, CheckFile)
    print("[KEEPING]" + ShowFound.encode('ascii', 'ignore').decode('ascii')+ " " + CheckFile.encode('ascii', 'ignore').decode('ascii'))

####################################################################################
##  Get Files for Watched Shows
####################################################################################
for ShowNode in doc.getElementsByTagName("Directory"):
    directory = ShowNode.getAttribute("key")
    show = ShowNode.getAttribute("title")
    #from urllib.request import urlopen

    #ShowDoc = xml.dom.minidom.parse(urlopen(("http://" + Host + ":" + Port + directory)))
    ShowDoc = xml.dom.minidom.parseString(requests.get(("http://" + Host + ":" + Port + directory), headers={'X-Plex-Token': plex_server_token}).text)


    for VideoNode in ShowDoc.getElementsByTagName("Video"):
      view = VideoNode.getAttribute("viewCount")
      if view == '':
        view = 0
      view = int(view)
      MediaNode = VideoNode.getElementsByTagName("Media")
      for Media in MediaNode:
        PartNode = Media.getElementsByTagName("Part")
        for Part in PartNode:
          file = Part.getAttribute("file")
          if view > 0:
              if os.path.isfile(file):
                CheckShows(file);
              else:
                print("##[NOT FOUND] " + file)

# copy 5* movies to network drive
# loop through movies to find ones that are in the pny256 drive
# for VideoNode in movie_doc.getElementsByTagName("Video"):
#   MediaNode = VideoNode.getElementsByTagName("Media")
#   for Media in MediaNode:
#     PartNode = Media.getElementsByTagName("Part")
#     for Part in PartNode:
#       file = Part.getAttribute("file")
#       destination_file = NetworkMoviePath + os.path.basename(file)
#       if 'pny256' in file:
#         shutil.move(file, destination_file)
#         print('%s moved to NAS' % file)


####################################################################################
##  Check Shows And Delete If Configured
####################################################################################    
print("")
print("")
print("")
print("Summary -- Script Completed Successfully")
print("")
print("")
print("  Total File Count  " + str(FileCount))
print("  Kept Show Files   " + str(ShowsCount))
print("  On Deck Files     " + str(OnDeckCount))
print("  Deleted Files     " + str(DeleteCount))
print("  Flagged Files     " + str(FlaggedCount))
print("")
print("")
print("")