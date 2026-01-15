# protothing
<sub>i have no idea to name this project</sub>

Modular app platform for LED matrix displays

> [!WARNING]
> This project is in early development. Expect breaking changes and incomplete features
> Hardware guides and schematics are not yet available

## Features
- Modular app architecture
- Web UI 
- Supports various LED matrix hardware
- Real-time rendering with sprites, text, effects and transitions

## Development Setup
### Prerequisites
- Python 3.10+
- Node.js 22+

#### Backend Setup
```
cd app
pip3 install -r requirements.txt
mv config.example.yaml config.yaml
nano config.yaml # if needed
```

#### Frontend Setup
```
cd webui
pnpm install
pnpm build
```
#### Running the Application
```
cd app
python3 main.py
```
You can access the web UI at `http://localhost:8000`

#### Frontend Development
```
cd webui
nano .env # set NEXT_PUBLIC_API_URL=http://localhost:8000
pnpm dev 
```
You can access the web UI with hot reload at `http://localhost:3000`

## Hardware Setup
Will be someday
