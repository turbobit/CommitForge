import { describe, expect, it } from "vitest";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdtemp, mkdir, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { detectInstall } from "../src/core/detect";
import { loadManifest } from "../src/core/payload";
import { spawnProbe } from "../src/core/python";

const run = promisify(execFile);

const payloadRoot = join(__dirname, "..", "payload");

/**
 * detect.ts의 core 경로 비교가 install.py의 실제 출력과 어긋나지 않는지 확인하는
 * 유일한 구조적 테스트다. detect.test.ts의 다른 픽스처들은 SKILL.md를 직접 써서
 * 양쪽에 같은 어휘적 경로를 넣기 때문에, install.py와 detect.ts가 경로를 계산하는
 * 방식 자체가 어긋나는 회귀(예: 심링크 미해석)를 원리적으로 잡지 못한다. 여기서는
 * 번들된 payload/install.py를 실제로 실행해 이 클래스의 결함을 구조적으로 막는다.
 *
 * payload/가 없으면(빌드 전) 이 테스트는 건너뛰지 않고 그대로 실패한다 — `npm test`는
 * sync-payload를 먼저 실행하므로 정상 환경에서는 항상 존재해야 한다.
 */
describe("install.py -> detectInstall 통합", () => {
  it(
    "실제 install.py로 설치한 결과를 detectInstall이 ok로 판정한다",
    async (ctx) => {
      const python = (await spawnProbe("python3"))
        ? "python3"
        : (await spawnProbe("python"))
          ? "python"
          : null;

      if (python === null) {
        console.warn(
          "[skip] 이 환경에서는 python3/python을 찾지 못해 install.py 통합 테스트를 건너뜁니다",
        );
        ctx.skip();
        return;
      }

      const tempRoot = await mkdtemp(join(tmpdir(), "cf-install-integration-"));
      // 워크스페이스를 심링크 경로로 열었을 때를 재현한다 (예: macOS /tmp -> /private/tmp,
      // 심링크된 프로젝트 디렉터리). install.py는 --target을 realpath로 해석해 core_path를
      // 기록하므로, 이 별칭 디렉터리로 설치·판정을 모두 수행해야 어휘적 경로만 비교하는
      // 회귀를 잡을 수 있다. (실제 디렉터리와 별칭 디렉터리는 이름 자체가 달라, macOS의
      // /var·/private/var처럼 한쪽이 다른 쪽의 접미사가 되는 우연한 문자열 일치로 착시
      // 통과가 생기지 않는다.)
      const realProjectDir = join(tempRoot, "real-project");
      const aliasProjectDir = join(tempRoot, "alias-project");
      await mkdir(realProjectDir, { recursive: true });
      await symlink(realProjectDir, aliasProjectDir, "dir");

      try {
        await run(python, [
          join(payloadRoot, "install.py"),
          "--scope",
          "project",
          "--target",
          aliasProjectDir,
        ]);

        const manifest = await loadManifest(payloadRoot);
        const report = await detectInstall(join(aliasProjectDir, ".claude"), manifest, "project");

        expect(report.missingFiles).toEqual([]);
        expect(report.mismatchedFiles).toEqual([]);
        expect(report.corePathOk).toBe(true);
        expect(report.state).toBe("ok");
      } finally {
        await rm(tempRoot, { recursive: true, force: true });
      }
    },
  );
});
