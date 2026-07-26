# `/cca` 반복 중 Graceful Stop

## 1. 요청과 latch

`/cca`가 실행 중일 때 사용자가 새 메시지로 `종료 예약`, `현재 반복 후 종료`,
`graceful stop` 또는 같은 의미를 명시하면 lead는
`GRACEFUL_STOP_REQUESTED=true`로 고정한다. 한 번 설정한 latch는 현재 실행에서
해제하지 않는다. 이는 강제 종료나 성공 요청이 아니라 **안전 경계에서 미완료
종료**하라는 요청이다.

lead는 Team 결과 집계 전, source 수정 전후, 새 반복 시작 전, 검증·staging·commit
전에 새 사용자 메시지에 이 요청이 있는지 확인한다. 이미 실행 중인 단일 tool call을
취소하거나 파일을 rollback하지 않는다.

최초 리뷰와 모든 재리뷰를 시작할 때 lead는 다음 형식으로 먼저 안내한다.

```text
리뷰 반복 <현재>/<--iterations 상한> 시작 — 종료 예약: 진행 중 “종료 예약” 또는 “현재 반복 후 종료”를 입력하면 현재 안전 경계에서 종료합니다.
```

Team을 생략하거나 subagent로 fallback해도 안내를 생략하지 않는다. 같은 반복에서
reviewer batch가 여러 번 나뉘는 경우에는 첫 batch 전에 한 번만 출력한다.

## 2. 요청 시점별 안전 경계

- read-only Team 리뷰 중: 현재 task 결과를 가능한 범위에서 회수하고 모든 teammate를
  종료한다. 새 수정·Team·검증·commit을 시작하지 않는다.
- Team 종료 후, 수정 전: 즉시 종료 절차로 이동한다.
- lead 수정 중 또는 수정 직후: 현재의 국소 수정 단위를 마치고 fingerprint를
  갱신한다. 새 read-only Team으로 그 fingerprint의 전체 diff 재리뷰까지만 완료한
  뒤 Team을 종료한다. 추가 수정 반복은 시작하지 않는다.
- 재리뷰 중: 결과를 집계하고 Team을 종료한 뒤 추가 수정 없이 종료한다.
- 검증 이후 commit 전: staging과 commit을 시작하지 않는다.
- commit unit 실행 중에는 이미 시작한 Git 명령을 되돌리지 않는다. 생성된 commit과
  남은 상태를 보고하고 다음 unit은 시작하지 않는다.

Team task가 timeout 또는 coordination 실패로 terminal 상태가 되지 않으면 종료를
무기한 기다리지 않는다. 미완료 task를 취소·종료하고 해당 관점을 `UNKNOWN`으로
기록한다.

## 3. Guard와 보고

Graceful Stop은 전체 파이프라인 성공이 아니므로 `finish`하지 않는다. lead가 모든
teammate 종료를 확인한 뒤 자신의 session·token·snapshot으로 Guard `abort`를
실행하여 lock을 해제하고 snapshot을 보존한다.

최종 보고에는 다음을 포함한다.

- 종료 요청을 인식한 단계와 완료한 안전 경계
- 마지막 검토 fingerprint와 이후 source 변경 여부
- 완료·미완료·`UNKNOWN` reviewer/task
- 자동 수정, 검증, staging, 생성된 commit
- snapshot 보존 경로와 lock 해제 성공 여부
- 재개 시 `/cca`를 새로 실행해야 한다는 안내

`abort` 실패 시 성공이나 정상 종료로 보고하지 않는다. lock 경로와 소유 session,
실패 명령의 필수 인자를 마스킹하지 말고 정확히 보고하되 token 값은 노출하지 않는다.
