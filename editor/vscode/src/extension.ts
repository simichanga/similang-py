/**
 * Similang VS Code Extension
 *
 * Provides:
 *  - LSP client (diagnostics, hover, completion, go-to-def, symbols)
 *  - Run command (execute .simi files via the Similang compiler)
 *  - Show IR command
 */
import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel;

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

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand("similang.run", () => runFile(false)),
    vscode.commands.registerCommand("similang.runOptimized", () =>
      runFile(true)
    ),
    vscode.commands.registerCommand("similang.showIR", () => showIR()),
    vscode.commands.registerCommand("similang.restartServer", () =>
      restartServer(context)
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
      filePath,
      `-O${optLevel}`,
    ];

    const terminal = vscode.window.createTerminal({
      name: `Similang: ${path.basename(filePath)}`,
      cwd: projectRoot,
    });
    terminal.show();
    terminal.sendText(`${pythonPath} ${args.join(" ")}`);
  });
}

function showIR(): void {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "similang") {
    vscode.window.showWarningMessage("No Similang file is open.");
    return;
  }

  editor.document.save().then(async () => {
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
    const cmd = `${pythonPath} main.py "${filePath}" --no-run --debug`;

    exec(
      cmd,
      { cwd: projectRoot },
      (err: Error | null, stdout: string, stderr: string) => {
        const text = stdout || stderr || (err ? err.message : "No output");
        vscode.workspace
          .openTextDocument({ content: text, language: "llvm" })
          .then((doc) => vscode.window.showTextDocument(doc));
      }
    );
  });
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
        require("fs").accessSync(mainPy);
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
