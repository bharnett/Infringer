Infringer
=========

This is a Python 3 & Cherrypy program to manage and retrieve TV & movie information of web sites.  It uses the following Python libraries so make sure you
install those first before attempting to run the program!  It isn't much good with <a href="http://board.jdownloader.org/showthread.php?t=54725">JDownloader2</a> and its .crawljob file processing ability.  Make sure you set up the folder watch and auto-confirm settings for full automation.
<ul>
<li>Cherrypy</li>
<li>Mako</li>
<li>MechanicalSoup</li>
<li>SQLAlchemy</li>
<li>TVDB_API</li>
</ul>

All javascript references are held in CDNs:
<ul>
<li>Bootstrap 3</li>
<li>jQuery 1.11</li>
<li>jQuery Validate 3</li>
<li>pNotify</li>
<li>nicescroll</li>
</ul>

Once you've downloaded the repo, just call 'python3 [DIRECTORY/OF/REPO]/Infringer/infringe.py' and it will start right up. The default listener is 0.0.0.0:8080 so just go to localhost:8080 and you'll be ready to roll.  

For automation, I recommend <a href="">Launch Control for Mac</a> or Task Scheduler for Windows.  The 'LinkRetriever.py' file can be called independantly to scan the web.  'webutils.py' can be called independantly to refresh all shows for new/updated episodes.  
