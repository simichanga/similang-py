/**
 * Compiler Explorer webview panel for Similang.
 *
 * Shows:
 *  - Left: Original source code (line numbers)
 *  - Right: Generated LLVM IR (line numbers)
 *  - Hovering source line highlights mapped IR lines (and vice versa)
 *  - Click to scroll and focus
 *  - Auto-refreshes on file save
 */

import * as path from "path";
import * as vscode from "vscode";
import { exec } from "child_process";
import * as fs from "fs";

export class CompilerExplorerPanel {
  public static readonly viewType = "similang.compilerExplorer";
  private static instance: CompilerExplorerPanel | undefined;

  private readonly panel: vscode.WebviewPanel;
  private readonly extensionUri: vscode.Uri;
  private saveWatcher: vscode.Disposable | undefined;
  private lastEditor: vscode.TextEditor | undefined;
  private lastConfig: vscode.WorkspaceConfiguration | undefined;

  private constructor(
    panel: vscode.WebviewPanel,
    extensionUri: vscode.Uri,
    context: vscode.ExtensionContext
  ) {
    this.panel = panel;
    this.extensionUri = extensionUri;

    this.panel.onDidDispose(() => {
      this.saveWatcher?.dispose();
      CompilerExplorerPanel.instance = undefined;
    });

    // Auto-refresh on save of .simi files
    this.saveWatcher = vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.languageId === "similang" && this.lastEditor && this.lastConfig) {
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor && activeEditor.document === doc) {
          this.lastEditor = activeEditor;
        }
        this.loadFile(this.lastEditor, this.lastConfig);
      }
    });

    context.subscriptions.push(this.saveWatcher);
  }

  public static createOrShow(
    extensionUri: vscode.Uri,
    editor: vscode.TextEditor,
    config: vscode.WorkspaceConfiguration,
    context: vscode.ExtensionContext
  ): void {
    const column = vscode.ViewColumn.Beside;

    if (CompilerExplorerPanel.instance) {
      CompilerExplorerPanel.instance.panel.reveal(column);
      CompilerExplorerPanel.instance.lastEditor = editor;
      CompilerExplorerPanel.instance.lastConfig = config;
      CompilerExplorerPanel.instance.loadFile(editor, config);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      CompilerExplorerPanel.viewType,
      "Similang Compiler Explorer",
      column,
      {
        enableScripts: true,
        localResourceRoots: [],
        retainContextWhenHidden: true,
      }
    );

    CompilerExplorerPanel.instance = new CompilerExplorerPanel(
      panel,
      extensionUri,
      context
    );
    CompilerExplorerPanel.instance.lastEditor = editor;
    CompilerExplorerPanel.instance.lastConfig = config;
    CompilerExplorerPanel.instance.loadFile(editor, config);
  }

  private loadFile(
    editor: vscode.TextEditor,
    config: vscode.WorkspaceConfiguration
  ): void {
    const filePath = editor.document.uri.fsPath;
    const sourceText = editor.document.getText();
    const pythonPath = config.get<string>("pythonPath", "python");
    const projectRoot = resolveProjectRoot(config);

    if (!projectRoot) {
      this.panel.webview.html = this.getErrorHtml(
        "Project root not found. Set similang.projectRoot in settings."
      );
      return;
    }

    // Show a loading indicator
    this.panel.webview.html = this.getLoadingHtml();

    const optLevel = config.get<number>("optimizationLevel", 2);

    // Run two commands: first emit IR, then emit source map JSON
    // Use a separator in stdout to split the outputs
    const separator = "___SIMILANG_SRCMAP_SEPARATOR___";
    const baseArgs = `main.py "${filePath}" --no-run -O ${optLevel}`;
    const cmd = [
      `"${pythonPath}" ${baseArgs} --emit-ir`,
      `echo ${separator}`,
      `"${pythonPath}" ${baseArgs} --emit-source-map`,
    ].join(" && ");

    exec(
      cmd,
      { cwd: projectRoot, maxBuffer: 10 * 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err) {
          this.panel.webview.html = this.getErrorHtml(
            `Compilation failed:\n${stderr || err.message}`
          );
          return;
        }

        const parts = stdout.split(separator);
        const irText = (parts[0] || "").trim();
        let sourceMap: any = {};

        if (parts.length > 1) {
          const mapText = (parts[1] || "").trim();
          try {
            sourceMap = JSON.parse(mapText);
          } catch {
            // Source map parsing failed — show IR without mapping
          }
        }

        if (!irText) {
          this.panel.webview.html = this.getErrorHtml(
            `No IR output produced.\nstderr: ${stderr || "(none)"}`
          );
          return;
        }

        this.panel.webview.html = this.getWebviewHtml(
          sourceText,
          irText,
          sourceMap,
          path.basename(filePath)
        );
      }
    );
  }

  private getWebviewHtml(
    sourceText: string,
    irText: string,
    sourceMap: any,
    filename: string
  ): string {
    const sourceLines = sourceText.split("\n");
    const irLines = irText.split("\n");

    // Build mapping: source line → IR lines
    const srcToIr: Map<number, number[]> = new Map();
    const irToSrc: Map<number, number> = new Map();

    if (sourceMap.mappings) {
      for (const m of sourceMap.mappings) {
        irToSrc.set(m.ir_line, m.source_line);
        if (!srcToIr.has(m.source_line)) {
          srcToIr.set(m.source_line, []);
        }
        srcToIr.get(m.source_line)!.push(m.ir_line);
      }
    }

    // Build JSON mapping data for the script
    const srcToIrJson: { [key: string]: number[] } = {};
    srcToIr.forEach((vals, srcLine) => {
      srcToIrJson[srcLine.toString()] = vals;
    });
    const irToSrcJson: { [key: string]: number } = {};
    irToSrc.forEach((srcLine, irLine) => {
      irToSrcJson[irLine.toString()] = srcLine;
    });

    const sourceHtml = sourceLines
      .map((line, i) => {
        const lineNo = i + 1;
        const hasMappings = srcToIr.has(lineNo);
        return `
          <div class="line ${hasMappings ? "has-mapping" : ""}" data-line="${lineNo}">
            <span class="line-number">${lineNo}</span>
            <span class="line-content">${escapeHtml(line)}</span>
          </div>`;
      })
      .join("");

    const irHtml = irLines
      .map((line, i) => {
        const lineNo = i + 1;
        const hasMapping = irToSrc.has(lineNo);
        return `
          <div class="line ${hasMapping ? "has-mapping" : ""}" data-line="${lineNo}">
            <span class="line-number">${lineNo}</span>
            <span class="line-content">${escapeHtml(line)}</span>
          </div>`;
      })
      .join("");

    const coveragePercent = sourceMap.stats
      ? Math.round(sourceMap.stats.coverage * 100)
      : 0;
    const mappedCount = sourceMap.stats?.mapped_ir_lines || 0;
    const totalCount = sourceMap.stats?.total_ir_lines || irLines.length;

    return /* html */ `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          * { box-sizing: border-box; }
          body {
            margin: 0;
            padding: 0;
            font-family: var(--vscode-editor-font-family, 'Monaco', 'Menlo', 'Courier New', monospace);
            font-size: var(--vscode-editor-font-size, 12px);
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
          }
          .toolbar {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 4px 12px;
            background: var(--vscode-titleBar-activeBackground, var(--vscode-editor-background));
            border-bottom: 1px solid var(--vscode-panel-border);
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
            flex-shrink: 0;
          }
          .toolbar .filename {
            font-weight: bold;
            color: var(--vscode-foreground);
          }
          .toolbar .stat {
            padding: 1px 6px;
            border-radius: 3px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            font-size: 10px;
          }
          .container {
            display: flex;
            width: 100%;
            flex: 1;
            overflow: hidden;
          }
          .panel {
            flex: 1;
            overflow: auto;
            border-right: 1px solid var(--vscode-panel-border);
            padding: 0;
          }
          .panel:last-child {
            border-right: none;
          }
          .title {
            position: sticky;
            top: 0;
            background: var(--vscode-editor-background);
            border-bottom: 1px solid var(--vscode-panel-border);
            padding: 4px 8px;
            font-weight: bold;
            font-size: 11px;
            color: var(--vscode-foreground);
            z-index: 10;
          }
          .content {
            padding: 0;
          }
          .line {
            display: flex;
            padding: 0 4px;
            line-height: 1.5;
            cursor: pointer;
            transition: background-color 0.15s;
          }
          .line:hover {
            background: var(--vscode-editor-hoverHighlightBackground);
          }
          .line.highlighted {
            background: rgba(255, 214, 102, 0.15);
          }
          .line.highlighted-strong {
            background: rgba(255, 214, 102, 0.3);
          }
          .line.has-mapping .line-number {
            color: var(--vscode-editorLineNumber-activeForeground);
          }
          .line-number {
            display: inline-block;
            width: 40px;
            text-align: right;
            margin-right: 8px;
            color: var(--vscode-editorLineNumber-foreground);
            flex-shrink: 0;
            user-select: none;
          }
          .line-content {
            white-space: pre;
            word-wrap: break-word;
            flex: 1;
          }
        </style>
      </head>
      <body>
        <div class="toolbar">
          <span class="filename">${escapeHtml(filename)}</span>
          <span>|</span>
          <span>Coverage: <span class="stat">${coveragePercent}% (${mappedCount}/${totalCount} IR lines)</span></span>
          <span>|</span>
          <span>Mappings: <span class="stat">${sourceMap.mappings?.length || 0}</span></span>
          <span style="flex:1"></span>
          <span style="opacity:0.6">Hover to highlight · Click to scroll · Auto-refreshes on save</span>
        </div>
        <div class="container">
          <div class="panel" id="source-panel">
            <div class="title">Source (similang)</div>
            <div class="content" id="source">${sourceHtml}</div>
          </div>
          <div class="panel" id="ir-panel">
            <div class="title">LLVM IR (-O${sourceMap.stats ? "" : ""}${coveragePercent > 0 ? "" : ""})</div>
            <div class="content" id="ir">${irHtml}</div>
          </div>
        </div>
        <script>
          const srcToIr = ${JSON.stringify(srcToIrJson)};
          const irToSrc = ${JSON.stringify(irToSrcJson)};

          const sourcePanel = document.getElementById('source');
          const irPanel = document.getElementById('ir');
          const sourceLinesEl = sourcePanel.querySelectorAll('.line');
          const irLinesEl = irPanel.querySelectorAll('.line');

          function clearHighlights() {
            sourceLinesEl.forEach(l => { l.classList.remove('highlighted', 'highlighted-strong'); });
            irLinesEl.forEach(l => { l.classList.remove('highlighted', 'highlighted-strong'); });
          }

          // Hover IR → highlight source
          irLinesEl.forEach(lineEl => {
            lineEl.addEventListener('mouseenter', () => {
              clearHighlights();
              const irLine = lineEl.getAttribute('data-line');
              const srcLine = irToSrc[irLine];
              if (srcLine !== undefined) {
                lineEl.classList.add('highlighted-strong');
                const srcEl = sourcePanel.querySelector('[data-line="' + srcLine + '"]');
                if (srcEl) srcEl.classList.add('highlighted-strong');
                const otherIrLines = srcToIr[srcLine] || [];
                otherIrLines.forEach(otherIr => {
                  const otherEl = irPanel.querySelector('[data-line="' + otherIr + '"]');
                  if (otherEl && otherEl !== lineEl) otherEl.classList.add('highlighted');
                });
              }
            });
          });

          // Hover source → highlight IR
          sourceLinesEl.forEach(lineEl => {
            lineEl.addEventListener('mouseenter', () => {
              clearHighlights();
              const srcLine = lineEl.getAttribute('data-line');
              const mappedIrLines = srcToIr[srcLine] || [];
              if (mappedIrLines.length > 0) {
                lineEl.classList.add('highlighted-strong');
                mappedIrLines.forEach(irLine => {
                  const irEl = irPanel.querySelector('[data-line="' + irLine + '"]');
                  if (irEl) irEl.classList.add('highlighted');
                });
              }
            });
          });

          // Click source → scroll to first mapped IR line
          sourceLinesEl.forEach(lineEl => {
            lineEl.addEventListener('click', () => {
              const srcLine = lineEl.getAttribute('data-line');
              const mappedIrLines = srcToIr[srcLine] || [];
              if (mappedIrLines.length > 0) {
                const irEl = irPanel.querySelector('[data-line="' + mappedIrLines[0] + '"]');
                if (irEl) irEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            });
          });

          // Click IR → scroll to mapped source line
          irLinesEl.forEach(lineEl => {
            lineEl.addEventListener('click', () => {
              const irLine = lineEl.getAttribute('data-line');
              const srcLine = irToSrc[irLine];
              if (srcLine !== undefined) {
                const srcEl = sourcePanel.querySelector('[data-line="' + srcLine + '"]');
                if (srcEl) srcEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            });
          });

          document.querySelector('.container').addEventListener('mouseleave', clearHighlights);
        </script>
      </body>
      </html>
    `;
  }

  private getLoadingHtml(): string {
    return /* html */ `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body {
            font-family: sans-serif;
            padding: 40px;
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
          }
          .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid var(--vscode-foreground);
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 12px;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
        </style>
      </head>
      <body>
        <div><span class="spinner"></span> Compiling&hellip;</div>
      </body>
      </html>
    `;
  }

  private getErrorHtml(message: string): string {
    return /* html */ `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body {
            font-family: sans-serif;
            padding: 20px;
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
          }
          .error {
            color: var(--vscode-editorError-foreground);
            white-space: pre-wrap;
            font-family: monospace;
          }
          .hint {
            margin-top: 16px;
            color: var(--vscode-descriptionForeground);
            font-size: 12px;
          }
        </style>
      </head>
      <body>
        <h3>Compilation Error</h3>
        <div class="error">${escapeHtml(message)}</div>
        <div class="hint">
          Make sure the Similang compiler project root is set correctly.<br>
          Check <strong>Settings &gt; similang.projectRoot</strong> or that your workspace contains <code>main.py</code>.
        </div>
      </body>
      </html>
    `;
  }
}

function escapeHtml(text: string): string {
  const map: { [key: string]: string } = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

function resolveProjectRoot(
  config: vscode.WorkspaceConfiguration
): string | undefined {
  const explicit = config.get<string>("projectRoot", "");
  if (explicit) {
    return explicit;
  }

  const folders = vscode.workspace.workspaceFolders;
  if (folders) {
    for (const folder of folders) {
      const mainPy = path.join(folder.uri.fsPath, "main.py");
      try {
        fs.accessSync(mainPy);
        return folder.uri.fsPath;
      } catch {
        //
      }
    }
    if (folders.length > 0) {
      return folders[0].uri.fsPath;
    }
  }

  return undefined;
}
