/**
 * Similang VS Code Extension
 *
 * Provides:
 *  - LSP client (diagnostics, hover, completion, go-to-def, symbols)
 *  - Run command (execute .simi files via the Similang compiler)
 *  - Show IR / Compiler Explorer commands
 *  - Status bar indicators
 *  - CodeLens for function declarations
 */
import * as path from "path";
import * as fs from "fs";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";
import { CompilerExplorerPanel } from "./compilerExplorer";

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel;
let statusBarItem: vscode.StatusBarItem;

// ---------------------------------------------------------------------------
// Activation
// ---------------------------------------------------------------------------
export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel("Similang");

  // Start LSP client
  const config = vscode.workspace.getConfiguration("similang");
  if (config.get<boolean>("lsp.enable", true)) {
    startLanguageClient(context, config);
  }

  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBarItem.command = "similang.run";
  context.subscriptions.push(statusBarItem);
  updateStatusBar();

  // Update status bar when editor changes
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(() => updateStatusBar())
  );

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("similang.run", () => runFile(false)),
    vscode.commands.registerCommand("similang.runOptimized", () =>
      runFile(true)
    ),
    vscode.commands.registerCommand("similang.showIR", () =>
      compilerExplorer(context)
    ),
    vscode.commands.registerCommand("similang.compilerExplorer", () =>
      compilerExplorer(context)
    ),
    vscode.commands.registerCommand("similang.restartServer", () =>
      restartServer(context)
    ),
    vscode.commands.registerCommand("similang.showSourceMap", () =>
      showSourceMap()
    )
  );

  // CodeLens provider for function declarations
  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider(
      { language: "similang", scheme: "file" },
      new SimilangCodeLensProvider()
    )
  );

  outputChannel.appendLine("Similang extension activated");
}

// ---------------------------------------------------------------------------
// Deactivation
// ---------------------------------------------------------------------------
export async function deactivate(): Promise<void> {
  if (client) {
    await client.stop();
    client = undefined;
  }
}

// ---------------------------------------------------------------------------
// Status Bar
// ---------------------------------------------------------------------------
function updateStatusBar(): void {
  const editor = vscode.window.activeTextEditor;
  if (editor && editor.document.languageId === "similang") {
    statusBarItem.text = "$(play) Similang";
    statusBarItem.tooltip = "Run this Similang file (Ctrl+Shift+R)";
    statusBarItem.show();
  } else {
    statusBarItem.hide();
  }
}

// ---------------------------------------------------------------------------
// LSP Client
// ---------------------------------------------------------------------------
function startLanguageClient(
  context: vscode.ExtensionContext,
  config: vscode.WorkspaceConfiguration
): void {
  const pythonPath = config.get<string>("pythonPath", "python");
  const projectRoot = resolveProjectRoot(config);

  if (!projectRoot) {
    vscode.window.showWarningMessage(
      "Similang: Could not determine project root. Set similang.projectRoot in settings."
    );
    return;
  }

  const serverOptions: ServerOptions = {
    command: pythonPath,
    args: ["-m", "lsp"],
    options: { cwd: projectRoot },
    transport: TransportKind.stdio,
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "similang" }],
    synchronize: {
      fileEvents:
        vscode.workspace.createFileSystemWatcher("**/*.simi"),
    },
    outputChannel,
    traceOutputChannel: outputChannel,
  };

  client = new LanguageClient(
    "similang",
    "Similang Language Server",
    serverOptions,
    clientOptions
  );

  client.start().then(
    () => outputChannel.appendLine("Similang LSP started"),
    (err) => {
      outputChannel.appendLine(`Similang LSP failed to start: ${err}`);
      vscode.window.showErrorMessage(
        `Similang LSP failed to start: ${err.message}`
      );
    }
  );

  context.subscriptions.push({ dispose: () => client?.stop() });
}

async function restartServer(
  context: vscode.ExtensionContext
): Promise<void> {
  if (client) {
    await client.stop();
    client = undefined;
  }
  const config = vscode.workspace.getConfiguration("similang");
  startLanguageClient(context, config);
  vscode.window.showInformationMessage("Similang LSP restarted");
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------
function runFile(optimized: boolean): void {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "similang") {
    vscode.window.showWarningMessage("No Similang file is open.");
    return;
  }

  // Save the file first
  editor.document.save().then(() => {
    const filePath = editor.document.uri.fsPath;
    const config = vscode.workspace.getConfiguration("similang");
    const pythonPath = config.get<string>("pythonPath", "python");
    const projectRoot = resolveProjectRoot(config);

    if (!projectRoot) {
      vscode.window.showErrorMessage(
        "Similang: Could not determine project root."
      );
      return;
    }

    const optLevel = optimized
      ? 3
      : config.get<number>("optimizationLevel", 2);

    const args = [
      "main.py",
      `"${filePath}"`,
      `-O ${optLevel}`,
    ];

    // Reuse or create a terminal
    const termName = "Similang";
    let terminal = vscode.window.terminals.find((t) => t.name === termName);
    if (!terminal) {
      terminal = vscode.window.createTerminal({
        name: termName,
        cwd: projectRoot,
      });
    }
    terminal.show();
    terminal.sendText(`${pythonPath} ${args.join(" ")}`);
  });
}

// ---------------------------------------------------------------------------
// Compiler Explorer / Show IR
// ---------------------------------------------------------------------------
function compilerExplorer(context: vscode.ExtensionContext): void {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "similang") {
    vscode.window.showWarningMessage("No Similang file is open.");
    return;
  }

  editor.document.save().then(() => {
    const config = vscode.workspace.getConfiguration("similang");
    CompilerExplorerPanel.createOrShow(
      context.extensionUri,
      editor,
      config,
      context
    );
  });
}

// ---------------------------------------------------------------------------
// Show Source Map — print the source map table in the output channel
// ---------------------------------------------------------------------------
function showSourceMap(): void {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "similang") {
    vscode.window.showWarningMessage("No Similang file is open.");
    return;
  }

  editor.document.save().then(() => {
    const filePath = editor.document.uri.fsPath;
    const config = vscode.workspace.getConfiguration("similang");
    const pythonPath = config.get<string>("pythonPath", "python");
    const projectRoot = resolveProjectRoot(config);

    if (!projectRoot) {
      vscode.window.showErrorMessage(
        "Similang: Could not determine project root."
      );
      return;
    }

    const { exec } = require("child_process");
    const optLevel = config.get<number>("optimizationLevel", 2);
    const cmd = `"${pythonPath}" main.py "${filePath}" --no-run --show-source-map -O ${optLevel}`;

    exec(
      cmd,
      { cwd: projectRoot },
      (err: any, stdout: string, stderr: string) => {
        if (err) {
          vscode.window.showErrorMessage(
            `Source map generation failed: ${stderr || err.message}`
          );
          return;
        }
        outputChannel.clear();
        outputChannel.appendLine("=== Similang Source Map ===");
        outputChannel.appendLine(stdout);
        outputChannel.show();
      }
    );
  });
}

// ---------------------------------------------------------------------------
// CodeLens — "Run | View IR" above each function declaration
// ---------------------------------------------------------------------------
class SimilangCodeLensProvider implements vscode.CodeLensProvider {
  public provideCodeLenses(
    document: vscode.TextDocument,
    _token: vscode.CancellationToken
  ): vscode.CodeLens[] {
    const lenses: vscode.CodeLens[] = [];
    const fnPattern = /^\s*fn\s+(\w+)\s*\(/;

    for (let i = 0; i < document.lineCount; i++) {
      const line = document.lineAt(i);
      const match = fnPattern.exec(line.text);
      if (match) {
        const fnName = match[1];
        const range = new vscode.Range(i, 0, i, line.text.length);

        if (fnName === "main") {
          lenses.push(
            new vscode.CodeLens(range, {
              title: "$(play) Run",
              command: "similang.run",
              tooltip: "Run this file",
            })
          );
        }

        lenses.push(
          new vscode.CodeLens(range, {
            title: "$(split-horizontal) Compiler Explorer",
            command: "similang.compilerExplorer",
            tooltip: "Open Compiler Explorer showing IR for this file",
          })
        );
      }
    }

    return lenses;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function resolveProjectRoot(
  config: vscode.WorkspaceConfiguration
): string | undefined {
  // 1. Explicit setting
  const explicit = config.get<string>("projectRoot", "");
  if (explicit) {
    return explicit;
  }

  // 2. Workspace folder containing a main.py (the compiler driver)
  const folders = vscode.workspace.workspaceFolders;
  if (folders) {
    for (const folder of folders) {
      const mainPy = path.join(folder.uri.fsPath, "main.py");
      try {
        fs.accessSync(mainPy);
        return folder.uri.fsPath;
      } catch {
        // not found, try next
      }
    }
  }

  // 3. Fall back to first workspace folder
  if (folders && folders.length > 0) {
    return folders[0].uri.fsPath;
  }

  return undefined;
}
