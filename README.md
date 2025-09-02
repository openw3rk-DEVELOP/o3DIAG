<h2>o3DIAG – OBD-II Diagnostic Tool</h2>
<p>
o3DIAG is a diagnostic application designed to work with OBD-II vehicles through an ELM327 adapter.  
It provides an easy way to connect, read vehicle data, and interpret diagnostic trouble codes (DTCs).
</p>

<p>
<strong>Web:</strong><br>
<a href="https://o3diag.openw3rk.de">https://o3diag.openw3rk.de</a> / <a href="https://openw3rk.de">https://openw3rk.de</a><br>
<strong>o3DIAG Development Tool:</strong><br>
<a href="https://github.com/openw3rk-DEVELOP/o3DIAG_E-EE">https://github.com/openw3rk-DEVELOP/o3DIAG_E-EE</a><br>
<strong>For Feedback:</strong><br>
<a href="mailto:develop@openw3rk.de">develop@openw3rk.de</a></p>

<h3>Main Features</h3>

<p>
<strong>Connection Control</strong><br><br>
– Select communication port and baud rate.<br>
– Connect or disconnect the adapter with a single click.<br>
– Initialize the adapter automatically with the required AT commands.
</p>

<p>
<strong>Live Data Reading</strong><br><br>
– Read common engine parameters such as:<br>
&nbsp;&nbsp;• Engine RPM (PID 010C)<br>
&nbsp;&nbsp;• Vehicle Speed (PID 010D)<br>
&nbsp;&nbsp;• Coolant Temperature (PID 0105)<br>
&nbsp;&nbsp;• Engine Load (PID 0104)<br>
– Raw responses are automatically converted into real-world values (e.g., RPM in revolutions per minute,<br> temperature in °C, speed in km/h).
</p>

<p>
<strong>Diagnostic Trouble Codes (DTCs)</strong><br><br>
– Read stored error codes from the engine control unit.<br>
– Clear fault codes when required.<br>
– Codes are translated into plain-text descriptions for easier understanding.
</p>

<p>
<strong>P-Code Translation</strong><br><br>
– The program can look up diagnostic codes (P0000–P0999 and beyond) from an integrated script-based list.<br>
– Instead of showing just the raw code, the program displays the human-readable meaning of each fault.
</p>

<p>
<strong>User Interface</strong><br><br>
– Scrollable log window that shows all communication with the adapter.<br>
– Each entry is timestamped for clarity (at Beta 1.5).<br>
– Clear log function, with an automatic program banner shown again for orientation.<br>
– Info/Warning section with program details and disclaimers.
</p>

<h3>Summary</h3>

<p>
With o3DIAG, users can quickly access essential vehicle information, monitor live sensor data, and interpret engine fault codes in a clear and user-friendly interface.  
It is a practical tool for basic diagnostics and understanding of OBD-II data.
</p>

<h3>Information for developers</h3>

<p>
o3DIAG is open source and licensed under MIT-LICENSE.</p>
<h2>Compile:</h2>

<p>
Compiling o3DIAG is simple, using the following command:</p>
<pre><code>pyinstaller --onefile --windowed --icon=o3DIAG_ico.ico --add-data "o3DIAG_logo.png;." --add-data "THE_PCODES_LIST.o3script;." o3DIAG_VERSION.py</code></pre>
<p>Appropriate parameters such as "o3DIAG version" and the ".o3script" file for the P-codes list must be adjusted.</p><br>


<footer style="text-align: center; margin-top: 50px;">
   <img src="Version Beta 1.5/o3DIAG_logo.png" alt="Logo" width="120">
  <strong>Copyright (c) openw3rk INVENT</strong>
</footer>
