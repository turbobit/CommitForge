export class EventEmitter<T> {
  private handlers: Array<(value: T) => void> = [];
  readonly event = (handler: (value: T) => void) => {
    this.handlers.push(handler);
    return { dispose: () => {} };
  };
  fire(value: T): void {
    for (const handler of this.handlers) handler(value);
  }
  dispose(): void {
    this.handlers = [];
  }
}

export class ThemeIcon {
  constructor(
    public id: string,
    public color?: ThemeColor,
  ) {}
}

export class ThemeColor {
  constructor(public id: string) {}
}

export class TreeItem {
  description?: string;
  iconPath?: unknown;
  contextValue?: string;
  /** 실제 vscode.TreeItem과 같은 타입: string | MarkdownString | undefined. */
  tooltip?: string;
  /** 실제 vscode.Command와 같은 형태({ command, title, tooltip?, arguments? }). */
  command?: { command: string; title: string; tooltip?: string; arguments?: unknown[] };
  constructor(
    public label: string,
    public collapsibleState?: number,
  ) {}
}

export const TreeItemCollapsibleState = { None: 0, Collapsed: 1, Expanded: 2 };
export const StatusBarAlignment = { Left: 1, Right: 2 };
export const QuickPickItemKind = { Separator: -1, Default: 0 };

export const Disposable = {
  from: (...items: Array<{ dispose: () => void }>) => ({
    dispose: () => items.forEach((item) => item.dispose()),
  }),
};

export const workspace = {
  createFileSystemWatcher: () => ({
    onDidChange: () => ({ dispose: () => {} }),
    onDidCreate: () => ({ dispose: () => {} }),
    onDidDelete: () => ({ dispose: () => {} }),
    dispose: () => {},
  }),
  getConfiguration: () => ({ get: <T>(_key: string, fallback?: T) => fallback }),
  workspaceFolders: undefined as unknown,
};

export const window = {
  onDidChangeWindowState: () => ({ dispose: () => {} }),
  createStatusBarItem: () => ({
    text: "",
    tooltip: "",
    command: "",
    show: () => {},
    hide: () => {},
    dispose: () => {},
  }),
  createTreeView: () => ({ dispose: () => {} }),
  terminals: [] as unknown[],
};

export class RelativePattern {
  constructor(
    public base: unknown,
    public pattern: string,
  ) {}
}

export const Uri = {
  file: (path: string) => ({ fsPath: path, path, scheme: "file" }),
  joinPath: (base: { fsPath: string }, ...segments: string[]) => {
    const path = [base.fsPath, ...segments].join("/");
    return { fsPath: path, path, scheme: "file" };
  },
};
