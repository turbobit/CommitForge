import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm, symlink, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { detectInstall } from "../src/core/detect";
import { parseManifest, type Manifest } from "../src/core/payload";

const sha = (text: string) => createHash("sha256").update(text).digest("hex");

const AGENT_BODY = "agent body\n";
const CORE_BODY = "core body\n";

function buildManifest(coreTemplatePath: string): Manifest {
  return parseManifest(
    JSON.stringify({
      name: "CommitForge",
      version: "1.15.0",
      file_count: 3,
      files: [
        {
          path: ".claude/agents/cca-git-reviewer.md",
          size: AGENT_BODY.length,
          sha256: sha(AGENT_BODY),
        },
        {
          path: ".claude/skills/_git-atomic-core/guard.md",
          size: CORE_BODY.length,
          sha256: sha(CORE_BODY),
        },
        {
          path: ".claude/skills/cr/SKILL.md",
          size: coreTemplatePath.length,
          sha256: sha(coreTemplatePath),
        },
      ],
    }),
  );
}

/** 정상 설치 상태를 임시 디렉터리에 만든다. */
async function makeInstall(
  root: string,
  opts: {
    marker?: boolean;
    corePath?: string;
    hooks?: boolean;
    markerVersion?: string;
  } = {},
): Promise<string> {
  const claudeDir = join(root, ".claude");
  const corePath = opts.corePath ?? join(claudeDir, "skills", "_git-atomic-core");

  await mkdir(join(claudeDir, "agents"), { recursive: true });
  await mkdir(join(claudeDir, "skills", "_git-atomic-core"), { recursive: true });
  await mkdir(join(claudeDir, "skills", "cr"), { recursive: true });

  await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), AGENT_BODY);
  await writeFile(join(claudeDir, "skills", "_git-atomic-core", "guard.md"), CORE_BODY);
  await writeFile(
    join(claudeDir, "skills", "cr", "SKILL.md"),
    `---\nname: cr\nallowed-tools:\n  - Read\n---\n\n${corePath}/deep-review-protocol.md 를 읽는다\n`,
  );

  if (opts.marker !== false) {
    await writeFile(
      join(claudeDir, ".commitforge-install.json"),
      JSON.stringify({
        schema: "commitforge-install/v1",
        version: opts.markerVersion ?? "1.15.0",
        scope: "project",
        installed_at: "2026-09-11T08:12:03Z",
        python: "/usr/bin/python3",
        core_path: corePath,
      }),
    );
  }

  if (opts.hooks !== false) {
    await writeFile(
      join(claudeDir, "settings.local.json"),
      JSON.stringify({
        hooks: {
          SessionEnd: [
            {
              hooks: [
                {
                  type: "command",
                  command: `/usr/bin/python3 ${corePath}/scripts/session_lifecycle.py`,
                },
              ],
            },
          ],
        },
      }),
    );
  }
  return claudeDir;
}

describe("detectInstall", () => {
  let root: string;

  beforeEach(async () => {
    root = await mkdtemp(join(tmpdir(), "cf-detect-"));
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("설치가 없으면 missing이다", async () => {
    const report = await detectInstall(join(root, ".claude"), buildManifest("/x"), "project");

    expect(report.state).toBe("missing");
    expect(report.installedVersion).toBeNull();
  });

  it("CommitForge와 무관한 사용자 skill만 있어도 missing이다 (단일 앵커 의존 제거 회귀 방지)", async () => {
    const claudeDir = join(root, ".claude");
    await mkdir(join(claudeDir, "skills", "my-own-skill"), { recursive: true });
    await writeFile(
      join(claudeDir, "skills", "my-own-skill", "SKILL.md"),
      "---\nname: my-own-skill\ndescription: 나만 쓰는 skill\n---\n본문\n",
    );

    const report = await detectInstall(claudeDir, buildManifest("/x"), "project");

    expect(report.state).toBe("missing");
    expect(report.installedVersion).toBeNull();
  });

  it("정상 설치에서 skills/cr/SKILL.md 하나만 지워지면 corrupt다 (missing이 아님)", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await rm(join(claudeDir, "skills", "cr", "SKILL.md"));

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("corrupt");
    expect(report.missingFiles).toContain(".claude/skills/cr/SKILL.md");
  });

  it("정상 설치는 ok다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("ok");
    expect(report.installedVersion).toBe("1.15.0");
    expect(report.corePathOk).toBe(true);
    expect(report.hooksRegistered).toBe(true);
  });

  it("마커가 번들과 다른 버전이면 일부만 달라도 version-mismatch다", async () => {
    // 버전이 올라갈 때 모든 파일이 바뀌는 경우는 없다. 개수로 추정하면
    // 정상적인 버전 차이가 거의 항상 손상으로 보고된다.
    const claudeDir = await makeInstall(root, { markerVersion: "1.18.0" });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), "changed\n");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("version-mismatch");
    expect(report.installedVersion).toBe("1.18.0");
  });

  it("마커가 번들과 다른 버전이면 파일 누락도 version-mismatch다", async () => {
    // 번들 매니페스트에 있는 파일이 설치본에 없는 것은, 그 버전에서 삭제된
    // 파일일 수 있다. 손상으로 단정하지 않는다.
    const claudeDir = await makeInstall(root, { markerVersion: "1.18.0" });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await rm(join(claudeDir, "agents", "cca-git-reviewer.md"));

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("version-mismatch");
  });

  it("마커가 번들과 같은 버전인데 일부만 다르면 corrupt다", async () => {
    // 같은 버전인데 파일이 다르면 그것이 진짜 손상이다.
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), "changed\n");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("corrupt");
  });

  it("해시가 전부 다르면 version-mismatch다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), "changed\n");
    await writeFile(join(claudeDir, "skills", "_git-atomic-core", "guard.md"), "changed\n");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("version-mismatch");
    expect(report.mismatchedFiles).toHaveLength(2);
  });

  it("core 경로가 남을 가리키면 misconfigured다", async () => {
    const claudeDir = await makeInstall(root, { corePath: "/other/machine/_git-atomic-core" });

    const report = await detectInstall(
      claudeDir,
      buildManifest("/other/machine/_git-atomic-core"),
      "project",
    );

    expect(report.state).toBe("misconfigured");
    expect(report.corePathOk).toBe(false);
  });

  it(
    "core 경로가 심링크를 통과해도 ok로 판정한다 (install.py의 realpath 마킹과 " +
      "detect.ts의 어휘적 비교 불일치 회귀 방지)",
    async () => {
      // install.py:87은 core_path를 .resolve()(심링크 해석)로 기록한다. 워크스페이스가
      // 심링크로 열리면(예: macOS /tmp -> /private/tmp) detect.ts가 어휘적 경로만
      // 비교할 경우 정상 설치도 misconfigured로 오판한다.
      const realRoot = join(root, "real");
      const aliasRoot = join(root, "alias");
      await mkdir(realRoot, { recursive: true });
      await symlink(realRoot, aliasRoot, "dir");

      // install.py가 실제로 기록하는 값은 완전히 정규화된 realpath이므로, 픽스처도
      // 같은 방식으로 계산해야 한다 (그러지 않으면 임시 디렉터리 자체가 심링크를
      // 낀 경로(macOS /var -> /private/var)일 때 이 테스트가 잘못된 이유로 실패한다).
      const canonicalRealRoot = await realpath(realRoot);
      const corePath = join(canonicalRealRoot, ".claude", "skills", "_git-atomic-core");

      await makeInstall(realRoot, { corePath });

      const report = await detectInstall(
        join(aliasRoot, ".claude"),
        buildManifest(corePath),
        "project",
      );

      expect(report.corePathOk).toBe(true);
      expect(report.state).toBe("ok");
    },
  );

  it("hook이 없으면 misconfigured다", async () => {
    const claudeDir = await makeInstall(root, { hooks: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("misconfigured");
    expect(report.hooksRegistered).toBe(false);
  });

  it("파일이 누락되면 corrupt다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await rm(join(claudeDir, "agents", "cca-git-reviewer.md"));

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("corrupt");
    expect(report.missingFiles).toContain(".claude/agents/cca-git-reviewer.md");
  });

  it("마커가 없어도 해시가 맞으면 ok이고 번들 버전을 쓴다", async () => {
    const claudeDir = await makeInstall(root, { marker: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("ok");
    expect(report.installedVersion).toBe("1.15.0");
  });

  it("마커 버전이 번들과 달라도 해시가 맞으면 ok이되 경고를 남긴다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(
      join(claudeDir, ".commitforge-install.json"),
      JSON.stringify({
        schema: "commitforge-install/v1",
        version: "9.9.9",
        scope: "project",
        installed_at: "2026-01-01T00:00:00Z",
        python: "/usr/bin/python3",
        core_path: corePath,
      }),
    );

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("ok");
    expect(report.warnings.join(" ")).toMatch(/9\.9\.9/);
  });

  it("global 범위는 settings.json에서 hook을 찾는다", async () => {
    const claudeDir = await makeInstall(root, { hooks: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(
      join(claudeDir, "settings.json"),
      JSON.stringify({
        hooks: {
          SessionEnd: [
            {
              hooks: [
                { type: "command", command: `python3 ${corePath}/scripts/session_lifecycle.py` },
              ],
            },
          ],
        },
      }),
    );

    const report = await detectInstall(claudeDir, buildManifest(corePath), "global");

    expect(report.hooksRegistered).toBe(true);
    expect(report.state).toBe("ok");
  });

  it("손상된 settings JSON은 hook 미등록으로 보고 경고한다", async () => {
    const claudeDir = await makeInstall(root, { hooks: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(join(claudeDir, "settings.local.json"), "{ broken");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.hooksRegistered).toBe(false);
    expect(report.warnings.join(" ")).toMatch(/settings\.local\.json/);
  });

  it("잘못된 UTF-8 바이트가 있어도 raw bytes 해시가 일치하면 ok다 (문자열 디코딩 손상 방지)", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    // 유효하지 않은 UTF-8 바이트열 (lone continuation / overlong 조합).
    const invalidUtf8 = Buffer.from([0x68, 0x69, 0xff, 0xfe, 0x0a]);
    const relPath = ".claude/skills/_git-atomic-core/binary.md";
    await writeFile(join(claudeDir, "skills", "_git-atomic-core", "binary.md"), invalidUtf8);

    const rawHash = createHash("sha256").update(invalidUtf8).digest("hex");

    const manifest = parseManifest(
      JSON.stringify({
        name: "CommitForge",
        version: "1.15.0",
        file_count: 4,
        files: [
          {
            path: ".claude/agents/cca-git-reviewer.md",
            size: AGENT_BODY.length,
            sha256: sha(AGENT_BODY),
          },
          {
            path: ".claude/skills/_git-atomic-core/guard.md",
            size: CORE_BODY.length,
            sha256: sha(CORE_BODY),
          },
          {
            path: relPath,
            size: invalidUtf8.length,
            sha256: rawHash,
          },
          {
            path: ".claude/skills/cr/SKILL.md",
            size: corePath.length,
            sha256: sha(corePath),
          },
        ],
      }),
    );

    const report = await detectInstall(claudeDir, manifest, "project");

    expect(report.mismatchedFiles).toEqual([]);
    expect(report.state).toBe("ok");
  });

  it(
    "매니페스트에 10번째 명령이 있어도 corrupt가 아니라 ok로 판정한다 " +
      "(COMMAND_NAMES 정적 목록 드리프트 회귀 방지)",
    async () => {
      // install.py의 SKILLS 목록에만 명령이 추가되고(예: 이번 릴리스의 /cf, /cfr, /ccf처럼)
      // detect.ts 쪽이 여전히 정적 COMMAND_NAMES 9개만 "치환되는 SKILL.md"로 알고 있으면,
      // 새 명령의 SKILL.md가 exactEntries에 잘못 포함되어 해시 대조 대상이 된다. install.py는
      // 그 SKILL.md의 core 경로도 똑같이 치환하므로 해시가 달라지고, 정상 설치가 corrupt로
      // 오판된다.
      const claudeDir = join(root, ".claude");
      const corePath = join(claudeDir, "skills", "_git-atomic-core");

      await mkdir(join(claudeDir, "agents"), { recursive: true });
      await mkdir(join(claudeDir, "skills", "_git-atomic-core"), { recursive: true });
      await mkdir(join(claudeDir, "skills", "cr"), { recursive: true });
      await mkdir(join(claudeDir, "skills", "cx"), { recursive: true });

      await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), AGENT_BODY);
      await writeFile(join(claudeDir, "skills", "_git-atomic-core", "guard.md"), CORE_BODY);
      await writeFile(
        join(claudeDir, "skills", "cr", "SKILL.md"),
        `---\nname: cr\n---\n\n${corePath}/deep-review-protocol.md 를 읽는다\n`,
      );
      // cx는 아직 어떤 목록에도 하드코딩되지 않은, 새로 추가된 10번째 명령을 흉내낸다.
      // install.py라면 이 SKILL.md의 core 경로도 cr과 똑같이 치환했을 것이다.
      await writeFile(
        join(claudeDir, "skills", "cx", "SKILL.md"),
        `---\nname: cx\n---\n\n${corePath}/x-protocol.md 를 읽는다\n`,
      );
      await writeFile(
        join(claudeDir, ".commitforge-install.json"),
        JSON.stringify({
          schema: "commitforge-install/v1",
          version: "1.15.0",
          scope: "project",
          installed_at: "2026-09-11T08:12:03Z",
          python: "/usr/bin/python3",
          core_path: corePath,
        }),
      );
      await writeFile(
        join(claudeDir, "settings.local.json"),
        JSON.stringify({
          hooks: {
            SessionEnd: [
              {
                hooks: [
                  {
                    type: "command",
                    command: `/usr/bin/python3 ${corePath}/scripts/session_lifecycle.py`,
                  },
                ],
              },
            ],
          },
        }),
      );

      // 매니페스트의 SKILL.md sha256은 치환 전 원본(소스) 내용의 해시다. 설치본은 core
      // 경로가 치환돼 있으므로, 이 값과 그대로 비교하면 항상 불일치한다 — 그래서 SKILL.md는
      // 해시가 아니라 checkCorePaths의 의미 검증 대상이어야 한다.
      const manifest = parseManifest(
        JSON.stringify({
          name: "CommitForge",
          version: "1.15.0",
          file_count: 4,
          files: [
            {
              path: ".claude/agents/cca-git-reviewer.md",
              size: AGENT_BODY.length,
              sha256: sha(AGENT_BODY),
            },
            {
              path: ".claude/skills/_git-atomic-core/guard.md",
              size: CORE_BODY.length,
              sha256: sha(CORE_BODY),
            },
            {
              path: ".claude/skills/cr/SKILL.md",
              size: 1,
              sha256: sha("---\nname: cr\n---\n\n.claude/skills/_git-atomic-core/deep-review-protocol.md 를 읽는다\n"),
            },
            {
              path: ".claude/skills/cx/SKILL.md",
              size: 1,
              sha256: sha("---\nname: cx\n---\n\n.claude/skills/_git-atomic-core/x-protocol.md 를 읽는다\n"),
            },
          ],
        }),
      );

      const report = await detectInstall(claudeDir, manifest, "project");

      expect(report.mismatchedFiles).toEqual([]);
      expect(report.state).toBe("ok");
    },
  );
});
