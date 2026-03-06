# Lyra Android Setup

## One-time setup commands (in order)
pkg update --fix-broken -y
pkg install python git cmake ninja rust -y
export ANDROID_API_LEVEL=24
export PATH=$PATH:~/.cargo/bin
pip install numpy
pip install "groq==0.9.0" "httpx==0.27.0" "pydantic==1.10.13"
pip install spotipy google-auth google-auth-oauthlib google-api-python-client requests
pkg install termux-api -y

## Clone
git clone https://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@github.com/hardiksharma111/Lyra

## Keys
nano Keys.txt  # add your keys

## Run
python main.py