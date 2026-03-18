import discord
from discord.ext import commands
import subprocess
import psutil
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
auth_users = os.getenv("AUTHORIZED_USERS")
DIR = os.getenv("DIR")
RUN_BAT = os.getenv("RUN_BAT", "run.bat")
SERVER_URL = os.getenv("SERVER_URL")

if auth_users:
    auth_users = auth_users.strip("[]").replace(' ', '').replace('"', '').replace("'", '')
    AUTHORIZED_USER_IDS = [int(id) for id in auth_users.split(',') if id.strip()]
else:
    AUTHORIZED_USER_IDS = []

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!R:", intents=intents)

managed_process = None


def is_authorized():
    async def predicate(ctx):
        if not AUTHORIZED_USER_IDS or ctx.author.id in AUTHORIZED_USER_IDS:
            return True
        await ctx.send("Você não tem permissão para usar esse comando")
        return False
    return commands.check(predicate)


def _deepest_java(root_pid: int) -> psutil.Process | None:
    """
    Percorre a árvore de processos a partir de root_pid e retorna
    o processo Java que não tem filhos Java — esse é sempre o servidor
    real.

    A estrutura típica do NeoForge é:
        cmd.exe (run.bat)
            └── java.exe (Oracle javapath, launcher ~7MB)
                    └── java.exe (servidor real ~1GB)  ← retorna este

    O launcher é nó intermediário; o servidor é sempre nó final.
    """
    try:
        root = psutil.Process(root_pid)
        candidates = [root] + root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    java_procs = []
    for proc in candidates:
        try:
            if "java" in (proc.exe() or "").lower():
                java_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not java_procs:
        return None

    java_pids = {p.pid for p in java_procs}

    for proc in java_procs:
        try:
            child_pids = {c.pid for c in proc.children()}
            if not child_pids.intersection(java_pids):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return java_procs[-1]


def _find_bat_process() -> psutil.Process | None:
    if not DIR:
        return None

    dir_norm = os.path.normcase(os.path.abspath(DIR))

    for proc in psutil.process_iter(['pid', 'name', 'cwd']):
        try:
            name = (proc.info.get('name') or '').lower()
            if name not in ('cmd.exe', 'powershell.exe'):
                continue
            cwd = os.path.normcase(os.path.abspath(proc.info.get('cwd') or ''))
            if cwd != dir_norm:
                continue
            if _deepest_java(proc.pid):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return None


def get_server_process() -> psutil.Process | None:
    global managed_process

    # 1. Processo gerenciado pelo bot
    if managed_process is not None:
        try:
            if managed_process.poll() is None:
                java = _deepest_java(managed_process.pid)
                if java:
                    return java
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
        managed_process = None

    # 2. Scan por cmd.exe no diretório do servidor — cobre servidor iniciado
    bat = _find_bat_process()
    if bat:
        return _deepest_java(bat.pid)

    return None


def get_root_pid() -> int | None:
    global managed_process

    if managed_process is not None:
        try:
            if managed_process.poll() is None:
                return managed_process.pid
        except OSError:
            pass

    bat = _find_bat_process()
    if bat:
        return bat.pid

    return None


async def graceful_stop(ctx, timeout_seconds: int = 60) -> bool:
    global managed_process

    java_proc = get_server_process()
    if not java_proc:
        return True

    stop_via_stdin = False
    if managed_process is not None:
        try:
            if managed_process.poll() is None and managed_process.stdin:
                managed_process.stdin.write(b"stop\n")
                managed_process.stdin.flush()
                stop_via_stdin = True
        except (OSError, AttributeError):
            pass

    if not stop_via_stdin:
        try:
            java_proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(2)
        try:
            if not java_proc.is_running():
                break
        except psutil.NoSuchProcess:
            break

    still_alive = False
    try:
        still_alive = java_proc.is_running()
    except psutil.NoSuchProcess:
        still_alive = False

    if still_alive:
        await ctx.send("Servidor não encerrou no tempo esperado. Forçando encerramento...")
        root = get_root_pid()
        if root:
            try:
                root_proc = psutil.Process(root)
                for p in [root_proc] + root_proc.children(recursive=True):
                    try:
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except psutil.NoSuchProcess:
                pass
        managed_process = None
        return False

    managed_process = None
    return True


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print(f'Diretório do servidor: {DIR}')
    print(f'Arquivo de execução: {RUN_BAT}')
    await bot.change_presence(activity=discord.Game(name="Rorusvaldo Runner"))


@bot.command(name="start")
@is_authorized()
async def start_server(ctx):
    global managed_process

    if get_server_process():
        await ctx.send("O servidor já está em execução")
        return

    try:
        await ctx.send("Iniciando servidor...")
        bat_path = os.path.join(DIR, RUN_BAT)
        if not os.path.exists(bat_path):
            await ctx.send(f"Arquivo não encontrado: {bat_path}")
            return

        managed_process = subprocess.Popen(
            [bat_path],
            cwd=DIR,
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=os.environ.copy()
        )

        await ctx.send(f"Servidor iniciado (PID raiz: {managed_process.pid})")
        await ctx.send(f"Endereço do servidor: {SERVER_URL}")
        await ctx.send("Aguarde alguns segundos para o servidor carregar completamente.")

    except Exception as e:
        await ctx.send(f"Erro ao iniciar servidor: {str(e)}")


@bot.command(name="stop")
@is_authorized()
async def stop_server(ctx):
    if not get_server_process():
        await ctx.send("O servidor não está em execução")
        return

    await ctx.send("Encerrando servidor...")
    success = await graceful_stop(ctx, timeout_seconds=60)

    if success:
        await ctx.send("Servidor encerrado.")
    else:
        await ctx.send("Servidor encerrado forçadamente.")


@bot.command(name='status')
@is_authorized()
async def check_status(ctx):
    java_proc = get_server_process()

    if java_proc:
        try:
            cpu = java_proc.cpu_percent(interval=1)
            mem_mb = java_proc.memory_info().rss / 1024 / 1024
            source = "Gerenciado pelo bot" if managed_process else "Detectado externamente"

            embed = discord.Embed(title="Status do Servidor", color=0x00ff00)
            embed.add_field(name="Status", value="Online", inline=False)
            embed.add_field(name="PID (Java)", value=str(java_proc.pid), inline=True)
            embed.add_field(name="CPU", value=f"{cpu:.1f}%", inline=True)
            embed.add_field(name="RAM", value=f"{mem_mb:.0f} MB", inline=True)
            embed.add_field(name="Origem", value=source, inline=False)
            await ctx.send(embed=embed)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            await ctx.send("Servidor está rodando mas não foi possível obter detalhes.")
    else:
        embed = discord.Embed(title="Status do Servidor", color=0xff0000)
        embed.add_field(name="Status", value="Offline", inline=False)
        await ctx.send(embed=embed)


@bot.command(name='restart')
@is_authorized()
async def restart_server(ctx):
    await ctx.send("Reiniciando servidor...")

    if get_server_process():
        success = await graceful_stop(ctx, timeout_seconds=60)
        if success:
            await ctx.send("Servidor parado. Aguardando 5 segundos...")
        else:
            await ctx.send("Servidor encerrado forçadamente. Aguardando 5 segundos...")
        await asyncio.sleep(5)

    await start_server(ctx)


@bot.command(name="commands")
async def help_command(ctx):
    embed = discord.Embed(
        title="Comandos do Rorusvaldo Runner",
        description="Controle o servidor do mine remotamente via Rorusvaldo",
        color=0x00aaff
    )
    embed.add_field(name="!R:start", value="Inicia o servidor", inline=False)
    embed.add_field(name="!R:stop", value="Para o servidor salvando os dados dos jogadores", inline=False)
    embed.add_field(name="!R:status", value="Verifica o status do servidor", inline=False)
    embed.add_field(name="!R:restart", value="Reinicia o servidor", inline=False)
    embed.add_field(name="!R:commands", value="Mostra esta mensagem", inline=False)
    await ctx.send(embed=embed)


if __name__ == '__main__':
    if not TOKEN:
        print("ERRO: Token do Discord não configurado!")
        exit(1)

    print("Iniciando Rorusvaldo Runner...")
    bot.run(TOKEN)