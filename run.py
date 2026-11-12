import sys
import subprocess
import shutil
import time
import os
import signal
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.absolute()
BACKEND_DIR = PROJECT_ROOT / "backend"
LLM_DIR = PROJECT_ROOT / "llm_api"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
VENV_NAME = ".venv"

BACKEND_VENV = BACKEND_DIR / VENV_NAME
LLM_VENV = LLM_DIR / VENV_NAME

REQUIRED_TOOLS = {
    "python": "python",
    "node": "node",
    "npm": "npm",
    "tesseract": "tesseract"
}

IS_WINDOWS = sys.platform == "win32" or os.name == "nt"
PIDS = []

def run_command(cmd, cwd, capture=False, shell=True):
    if capture:
        result = subprocess.run(cmd, cwd=str(cwd), shell=shell, capture_output=True, text=True)
        return result.stdout.strip()
    else:
        subprocess.run(cmd, cwd=str(cwd), shell=shell, check=False)

def check_tool(name, cmd):
    if shutil.which(cmd) is None:
        print(f"[ERRO] {name} não encontrado no PATH. Instale {name}.")
        return False
    print(f"[OK] {name} encontrado.")
    return True

def ensure_venv_and_deps(dir_path, venv_path):
    if not venv_path.exists():
        print(f"Criando ambiente virtual em {dir_path.name}...")
        run_command(f"python -m venv {VENV_NAME}", dir_path)

    if shutil.which("uv") is not None:
        print(f"Usando 'uv sync' em {dir_path.name}...")
        run_command("uv sync", dir_path)
    else:
        if IS_WINDOWS:
            python_exe = venv_path / "Scripts" / "python.exe"
        else:
            python_exe = venv_path / "bin" / "python"
        print(f"Usando pip em {dir_path.name}...")
        run_command(f"{python_exe} -m pip install -e .", dir_path)

def ensure_node_deps(dir_path):
    node_modules = dir_path / "node_modules"
    if not node_modules.exists():
        print(f"Instalando dependências Node em {dir_path.name}...")
        run_command("npm install", dir_path)

def check_env_file():
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print("[AVISO] Arquivo .env não encontrado na raiz do projeto.")
        print("Crie um arquivo .env com as variáveis necessárias:")
        print("OLLAMA_HOST=https://ollama.com")
        print("OLLAMA_API_KEY=sua_chave_aqui")
        print("OLLAMA_AVAILABLE_MODELS=gemma3:4b,llama3.2")
        print("OLLAMA_VISION_MODELS=llama3.2-vision")
        print("OCR_SPACE_API_KEY=sua_chave_ocr")
        print("RAG_SERVICE_URL=http://localhost:8001")
        print("\nVocê pode copiar o arquivo .env.example se existir.\n")
        return False
    print("[OK] .env encontrado na raiz do projeto.")
    return True

def check_all():
    print("=== CHECKLIST DE REQUISITOS ===")
    ok = True
    for name, cmd in REQUIRED_TOOLS.items():
        if not check_tool(name, cmd):
            ok = False

    if not BACKEND_VENV.exists():
        print("[INFO] Ambiente virtual do backend será criado automaticamente.")
    if not LLM_VENV.exists():
        print("[INFO] Ambiente virtual da LLM API será criado automaticamente.")
    if not (FRONTEND_DIR / "node_modules").exists():
        print("[INFO] node_modules do frontend serão instalados automaticamente.")

    check_env_file()

    if ok:
        print("\n[SUCESSO] Ferramentas essenciais encontradas.")
    else:
        print("\n[ERRO] Algumas ferramentas essenciais não foram encontradas.")
    return ok

def install_all():
    print("\n=== CONFIGURANDO AMBIENTE ===")
    ensure_venv_and_deps(BACKEND_DIR, BACKEND_VENV)
    ensure_venv_and_deps(LLM_DIR, LLM_VENV)
    ensure_node_deps(FRONTEND_DIR)
    print("\n[SUCESSO] Ambiente configurado.")

def start_service_windows(name, command, cwd):
    cmd = f'cmd /k "cd /d {cwd} && {command}"'
    proc = subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
    PIDS.append(proc.pid)
    time.sleep(1)

def start_service_linux(name, command, cwd):
    cmd = f'cd "{cwd}" && {command}'
    if shutil.which("gnome-terminal"):
        proc = subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f'{cmd}; exec bash'])
    elif shutil.which("xterm"):
        proc = subprocess.Popen(["xterm", "-e", "bash", "-c", f'{cmd}; exec bash'])
    elif shutil.which("konsole"):
        proc = subprocess.Popen(["konsole", "-e", "bash", "-c", f'{cmd}; exec bash'])
    else:
        log_file = f"{name}.log"
        with open(log_file, "w") as f:
            proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, cwd=cwd)
        print(f"[INFO] {name} iniciado em segundo plano. Logs em {log_file}")
    if proc:
        PIDS.append(proc.pid)
    time.sleep(1)

def start_service(name, command, cwd):
    print(f"Iniciando {name}...")
    if IS_WINDOWS:
        start_service_windows(name, command, cwd)
    else:
        start_service_linux(name, command, cwd)

def stop_services():
    print("\n=== ENCERRANDO SERVIÇOS ===")
    if IS_WINDOWS:
        for pid in PIDS:
            try:
                subprocess.run(f"taskkill /PID {pid} /F", shell=True)
                print(f"Processo {pid} finalizado.")
            except:
                pass
    else:
        for pid in PIDS:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Processo {pid} finalizado.")
            except:
                pass
    print("Todos os serviços foram encerrados.")

def start_all():
    print("\n=== INICIANDO SERVIÇOS ===")
    if IS_WINDOWS:
        backend_python = BACKEND_VENV / "Scripts" / "python.exe"
        llm_python = LLM_VENV / "Scripts" / "python.exe"
        backend_cmd = f'{backend_python} app.py'
        llm_cmd = f'{llm_python} -m uvicorn main:app --host 0.0.0.0 --port 8001'
    else:
        backend_python = BACKEND_VENV / "bin" / "python"
        llm_python = LLM_VENV / "bin" / "python"
        backend_cmd = f'{backend_python} app.py'
        llm_cmd = f'{llm_python} -m uvicorn main:app --host 0.0.0.0 --port 8001'

    start_service("Backend", backend_cmd, BACKEND_DIR)
    start_service("LLM API", llm_cmd, LLM_DIR)
    start_service("Frontend", "npm start", FRONTEND_DIR)

    print("\nTodos os serviços foram iniciados.")
    print("Aguardando estabilização...")
    time.sleep(3)
    print("Acesse o frontend em http://localhost:3000")
    print("Pressione ENTER para encerrar este script e PARAR os serviços.")
    input()
    stop_services()

def main():
    print("=== INICIADOR DO PROJETO (Multiplataforma) ===")
    print("Este script verifica requisitos, configura o ambiente e inicia os serviços.")
    print("Nota: O Ollama é utilizado via API (cloud) – não requer instalação local.")
    print(f"Sistema operacional detectado: {'Windows' if IS_WINDOWS else 'Linux/Unix'}")
    print()

    if not check_all():
        resp = input("\nFerramentas essenciais não encontradas. Deseja continuar mesmo assim? (s/N): ").strip().lower()
        if resp != 's':
            print("Abortado.")
            sys.exit(1)

    install_all()
    start_all()

if __name__ == "__main__":
    main()