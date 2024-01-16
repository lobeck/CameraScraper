set -eo pipefail

rm lambda.zip
mkdir build

pip install --target build/ -r requirements.txt

cd build
zip -r ../lambda.zip .
cd ..
zip lambda.zip main.py

rm -rf build