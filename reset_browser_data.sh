c#!/bin/bash

echo "Changing directory to"
cd /c/Users/xtian/AppData/Local/BraveSoftware/Brave-Browser
pwd
echo "Removing profiles"

# rm -rf PlaywrightProfile
rm -rf JobstreetProfile
# rm -rf IndeedProfile

echo "Making directory profiles" 
# mkdir PlaywrightProfile
mkdir JobstreetProfile
# mkdir IndeedProfile

echo "Copying user data to each profile"
# cp -r 'User Data'/* PlaywrightProfile/
cp -r 'User Data'/* JobstreetProfile/
# cp -r 'User Data'/* IndeedProfile/

echo "Copied successfully"