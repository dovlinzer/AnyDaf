#!/bin/sh
# Usage: ./enable.sh /path/to/site-folder     (the folder you run `vercel deploy` from)
# Copies the gate into the site folder. Then, in that folder, YOU set the password and deploy:
#   vercel env add SITE_PASSWORD production      (type the password at the prompt)
#   vercel deploy --prod --yes
# To remove the gate: delete middleware.js from the site folder and redeploy.
set -e
[ -d "$1" ] || { echo "site folder not found: $1"; exit 1; }
cp "$(dirname "$0")/middleware.js" "$1/middleware.js"
echo "Copied middleware.js into $1. Next: cd $1 && vercel env add SITE_PASSWORD production && vercel deploy --prod --yes"
