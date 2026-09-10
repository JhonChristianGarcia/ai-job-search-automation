c#!/bin/bash

cd /c/Users/xtian/AppData/Local/BraveSoftware/Brave-Browser
pwd
ls
rm -rf PlaywrightProfile
ls
mkdir PlaywrightProfile
cp -r 'User Data'/* PlaywrightProfile/
ls PlaywrightProfile