# <img src="https://raw.githubusercontent.com/Lahrenheit/mirachangertol/refs/heads/main/IconGroup108_fucsia-6.png" width="50" height="50"/> Mira Changer Tool - Torrente On-Line

![Stars](https://img.shields.io/github/stars/Lahrenheit/mirachangertol?style=flat&label=Stars&color=ff69b4) ![Forks](https://img.shields.io/github/forks/Lahrenheit/mirachangertol?style=flat&label=Forks&color=orange) ![Watchers](https://img.shields.io/github/watchers/Lahrenheit/mirachangertol?style=flat&label=Watchers&color=blue)
![Tamaño del repo](https://img.shields.io/github/repo-size/Lahrenheit/mirachangertol?style=flat) ![Última versión](https://img.shields.io/github/v/release/Lahrenheit/mirachangertol?style=flat&color=success)
![Descargas totales](https://img.shields.io/github/downloads/Lahrenheit/mirachangertol/total?style=flat&color=blue)

🌐 **[Español](#español) · [English](#english) · [Português](#português)**

Cambia la mirilla/crosshair de Torrente On-Line

![Screenshot 55](https://raw.githubusercontent.com/Lahrenheit/mirachangertol/refs/heads/main/preview1.png)






---

## Español

Programa para cambiar fácilmente la **Mira Normal** (`mira.tex`) y la **Mira Telescópica** (`PUNTOdeMIRA.tex`) dentro del `demo.vpk` de **Torrente Online**, viendo la textura antes de aplicarla.

Es un único archivo (`mira_tool.py`), sin dependencias externas y sin necesidad de ningún otro programa.

### Características

- **Visor de texturas** de la mira actual, con la mira candidata al lado y a tamaño real.
- **Desplegable de miras disponibles** dentro del VPK:
  - Mira Normal: todas las texturas que empiezan con `mira...`
  - Mira Telescópica: todas las que empiezan con `PUNTOdeMIRA...`
- **Aplicar la seleccionada**: copia la mira elegida sobre `mira.tex` / `PUNTOdeMIRA.tex`.
- **Reemplazar...**: cambia la mira actual por una textura externa (`.tex` o `.dds`). Hay un botón para cada mira.
- **Exportar** la mira actual o la seleccionada, a `.dds` o `.tex`.
- **Casilla "Ignorar transparencia (alfa)"** para ver el color puro de la textura.
- **Idiomas**: español, português e English, con selector arriba a la derecha. Recuerda tu elección.
- **Copia de seguridad** automática (`.bak`) del VPK antes del primer cambio.
- Si hay un error, se muestra en una ventana y se guarda en `mira_tool_error.log`.

### ⚠️ Formato DXT5

Las miras del juego son siempre **DXT5**. Para que el juego las lea correctamente:

- Al **importar** una textura que no sea DXT5, el programa la rechaza y no toca el VPK.
- Al **exportar** o **aplicar** una mira que no sea DXT5, el programa te avisa.

Al reemplazar con un `.dds`, se convierte a `.tex` (TeX2) en memoria: se conserva solo el nivel principal y se descartan los mipmaps. Tu `.dds` original no se modifica.

### Requisitos

- Python 3 con `tkinter` (viene incluido en el instalador oficial de python.org para Windows).

### Uso

```
python mira_tool.py
```

1. Pulsa **Leer** y elige tu `demo.vpk` (recuerda la última ruta).
2. En cada panel, elige una mira del desplegable y pulsa **Aplicar la seleccionada**, o pulsa **Reemplazar...** para usar un archivo externo.
3. Confirma el cambio. Listo.

Si la textura nueva pesa lo mismo que la actual, se escribe en el sitio. Si pesa distinto, se reconstruye el VPK completo (puede tardar un poco). En ambos casos se crea antes la copia `.bak`.

> Prueba primero con una copia de tu `demo.vpk`.

### Crear un .exe (auto-py-to-exe)

1. `pip install auto-py-to-exe` y ejecuta `auto-py-to-exe`.
2. **Script Location**: `mira_tool.py`
3. **Onefile**: One File · **Console Window**: Window Based (hide the console)
4. **Icon**: tu archivo `.ico` (ideal con 16×16, 32×32, 48×48 y 256×256). El programa usa ese icono en la barra de título, la barra de tareas y Alt+Tab.
5. Convert `.py` to `.exe`.

### Archivos de configuración

Se guardan en tu carpeta de usuario: `.mira_tool_cfg` (último VPK) y `.mira_tool_lang` (idioma).

### Créditos

El núcleo de lectura/escritura del VPK y de conversión TEX/DDS proviene de `vpk_tool v1.1`.
Proyecto no oficial, sin relación con los creadores de Torrente Online. Úsalo bajo tu responsabilidad y conserva siempre una copia de tu `demo.vpk`.

---

## English

A tool to easily change the **Normal Crosshair** (`mira.tex`) and the **Scope Crosshair** (`PUNTOdeMIRA.tex`) inside **Torrente Online**'s `demo.vpk`, previewing the texture before applying it.

It is a single file (`mira_tool.py`) with no external dependencies and no other program required.

### Features

- **Texture viewer** showing the current crosshair, with the candidate next to it at real size.
- **Dropdown of available crosshairs** inside the VPK:
  - Normal Crosshair: every texture starting with `mira...`
  - Scope Crosshair: every texture starting with `PUNTOdeMIRA...`
- **Apply selected**: copies the chosen crosshair over `mira.tex` / `PUNTOdeMIRA.tex`.
- **Replace...**: swaps the current crosshair for an external texture (`.tex` or `.dds`). One button per crosshair.
- **Export** the current or the selected crosshair as `.dds` or `.tex`.
- **"Ignore transparency (alpha)"** checkbox to see the raw colour of the texture.
- **Languages**: español, português and English, selector at the top right. Your choice is remembered.
- Automatic **backup** (`.bak`) of the VPK before the first change.
- Errors are shown in a window and saved to `mira_tool_error.log`.

### ⚠️ DXT5 format

The game's crosshairs are always **DXT5**. For the game to read them correctly:

- When **importing** a texture that is not DXT5, the tool rejects it and leaves the VPK untouched.
- When **exporting** or **applying** a crosshair that is not DXT5, the tool warns you.

When replacing with a `.dds`, it is converted to `.tex` (TeX2) in memory: only the main level is kept and mipmaps are dropped. Your original `.dds` is not modified.

### Requirements

- Python 3 with `tkinter` (included in the official python.org installer for Windows).

### Usage

```
python mira_tool.py
```

1. Press **Read** and choose your `demo.vpk` (the last path is remembered).
2. In each panel, pick a crosshair from the dropdown and press **Apply selected**, or press **Replace...** to use an external file.
3. Confirm the change. Done.

If the new texture has the same size as the current one, it is written in place. If the size differs, the whole VPK is rebuilt (this may take a moment). A `.bak` copy is always created first.

> Try it on a copy of your `demo.vpk` first.

### Build an .exe (auto-py-to-exe)

1. `pip install auto-py-to-exe` and run `auto-py-to-exe`.
2. **Script Location**: `mira_tool.py`
3. **Onefile**: One File · **Console Window**: Window Based (hide the console)
4. **Icon**: your `.ico` file (ideally with 16×16, 32×32, 48×48 and 256×256). The tool uses it in the title bar, the taskbar and Alt+Tab.
5. Convert `.py` to `.exe`.

### Configuration files

Stored in your user folder: `.mira_tool_cfg` (last VPK) and `.mira_tool_lang` (language).

### Credits

The VPK read/write core and the TEX/DDS conversion come from `vpk_tool v1.1`.
Unofficial project, not affiliated with the creators of Torrente Online. Use at your own risk and always keep a copy of your `demo.vpk`.

---

## Português

Programa para trocar facilmente a **Mira Normal** (`mira.tex`) e a **Mira Telescópica** (`PUNTOdeMIRA.tex`) dentro do `demo.vpk` do **Torrente Online**, vendo a textura antes de aplicá-la.

É um único arquivo (`mira_tool.py`), sem dependências externas e sem precisar de nenhum outro programa.

### Recursos

- **Visualizador de texturas** da mira atual, com a mira candidata ao lado e em tamanho real.
- **Lista de miras disponíveis** dentro do VPK:
  - Mira Normal: todas as texturas que começam com `mira...`
  - Mira Telescópica: todas as que começam com `PUNTOdeMIRA...`
- **Aplicar a selecionada**: copia a mira escolhida sobre `mira.tex` / `PUNTOdeMIRA.tex`.
- **Substituir...**: troca a mira atual por uma textura externa (`.tex` ou `.dds`). Há um botão para cada mira.
- **Exportar** a mira atual ou a selecionada, em `.dds` ou `.tex`.
- **Caixa "Ignorar transparência (alfa)"** para ver a cor pura da textura.
- **Idiomas**: español, português e English, com seletor no canto superior direito. Sua escolha é lembrada.
- **Cópia de segurança** automática (`.bak`) do VPK antes da primeira alteração.
- Se houver um erro, ele aparece em uma janela e é salvo em `mira_tool_error.log`.

### ⚠️ Formato DXT5

As miras do jogo são sempre **DXT5**. Para que o jogo as leia corretamente:

- Ao **importar** uma textura que não seja DXT5, o programa a rejeita e não mexe no VPK.
- Ao **exportar** ou **aplicar** uma mira que não seja DXT5, o programa avisa você.

Ao substituir com um `.dds`, ele é convertido para `.tex` (TeX2) na memória: só o nível principal é mantido e os mipmaps são descartados. Seu `.dds` original não é modificado.

### Requisitos

- Python 3 com `tkinter` (incluído no instalador oficial do python.org para Windows).

### Uso

```
python mira_tool.py
```

1. Clique em **Ler** e escolha seu `demo.vpk` (o último caminho é lembrado).
2. Em cada painel, escolha uma mira na lista e clique em **Aplicar a selecionada**, ou clique em **Substituir...** para usar um arquivo externo.
3. Confirme a alteração. Pronto.

Se a nova textura tiver o mesmo tamanho da atual, ela é gravada no lugar. Se o tamanho for diferente, o VPK inteiro é reconstruído (pode demorar um pouco). Em ambos os casos a cópia `.bak` é criada antes.

> Teste primeiro com uma cópia do seu `demo.vpk`.

### Criar um .exe (auto-py-to-exe)

1. `pip install auto-py-to-exe` e execute `auto-py-to-exe`.
2. **Script Location**: `mira_tool.py`
3. **Onefile**: One File · **Console Window**: Window Based (hide the console)
4. **Icon**: seu arquivo `.ico` (idealmente com 16×16, 32×32, 48×48 e 256×256). O programa usa esse ícone na barra de título, na barra de tarefas e no Alt+Tab.
5. Convert `.py` to `.exe`.

### Arquivos de configuração

Ficam na sua pasta de usuário: `.mira_tool_cfg` (último VPK) e `.mira_tool_lang` (idioma).

### Créditos

O núcleo de leitura/escrita do VPK e de conversão TEX/DDS vem do `vpk_tool v1.1`.
Projeto não oficial, sem relação com os criadores do Torrente Online. Use por sua conta e risco e sempre mantenha uma cópia do seu `demo.vpk`.

