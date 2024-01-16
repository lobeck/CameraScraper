set -eo pipefail

rm lambda.zip
mkdir build

pip install --target build/ bs4 requests # boto3 is already installed

cd build
zip -r ../lambda.zip .
cd ..
zip lambda.zip main.py

rm -rf build