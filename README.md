This is a Python 3 & Cherrypy program to manage and retrieve TV & movie information of web sites. It uses the following Python libraries so make sure you
install those first before attempting to run the program! It isn't much good with <a href="http://board.jdownloader.org/showthread.php?t=54725">JDownloader2</a> and its .crawljob file processing ability. Make sure you set up the folder watch and auto-confirm settings for full automation.
install those first before attempting to run the program! It isn't much good with jdownloader2 and its .crawljob file processing ability.
<ul>
<li>Cherrypy</li>
<li>Mako</li>
<li>MechanicalSoup</li>
<li>SQLAlchemy</li>
<li>APScheduler</li>
<li>TVDB_API</li>
</ul>

All javascript references are held in CDNs:
<ul>
<li>pNotify</li>
<li>nicescroll</li>
</ul>

<ul>
<li>Once you've downloaded the repo, just call 'python3 [DIRECTORY/OF/REPO]/Infringer/infringe.py' and it will start right up. The default listener is 127.0.0.1:8080 but can be changed in the config. Changing requires a full shutdown of Python and the terminal because I haven't figure this part out yet.</li>
<li>For automation, I recommend <a href="http://www.soma-zone.com/LaunchControl/">Launch Control for Mac</a> or Task Scheduler for Windows. The config allows you to configure a scan interval and weekly refresh of TVDB stuff automatically.  Updating those requires a restart of the program.  The 'LinkRetriever.py' file can also be called independently to scan the web while 'webutils.py' can be called independantly to refresh all shows for new/updated episodes.</li>
</ul>
