from pathlib import Path
import yaml
CONFIG=Path(__file__).parents[1]/'config'/'app.yaml'

def effective_config():
    return yaml.safe_load(CONFIG.read_text())
