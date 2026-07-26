@echo off
rem Start TWMS minimized for small Windows/JOSM proxy deployments.
start "twms" /MIN python -m twms %*
