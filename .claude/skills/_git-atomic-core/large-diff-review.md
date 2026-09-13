# 대규모 Diff 리뷰

기본 threshold 중 하나를 넘으면 shard mode를 사용한다.

- 변경 파일 40개
- hunk 200개
- 추가+삭제 3000줄

`.commitforge/review.yml`이 더 엄격한 값을 지정하면 해당 값을 사용한다.

## 판정과 시작 공지

- 실제로 계산한 file·hunk·changed line 값과 적용 threshold를 비교한다.
- 초과한 항목만 `실제값 > 적용 threshold` 형태로 보고한다. 계산하지 않은 값,
  기본값과 다른 임의 threshold, 단순 추정치는 공지에 넣지 않는다.
- 프로젝트 override가 있으면 정책 파일 경로와 override 값을 함께 밝힌다.
- shard mode와 Team 인원은 별개다. shard mode가 core 3명을 shard 수만큼
  늘린다는 뜻으로 표현하지 않는다.
- Agent Team 활성 상태이면 다음 형식으로 시작 구조를 함께 공지한다.

```text
대형 diff: files 53 > 40. domain/runtime shard + lead aggregator를 적용합니다.
리뷰 실행: Agent Team core 3명 + 활성 trigger specialist(목록).
```

아직 trigger 평가 전이면 specialist를 추측하지 말고 `평가 중`으로 표시한 뒤,
평가가 끝나면 `ACTIVE`·`N/A`·`UNKNOWN` 결과를 별도로 보고한다.

## 절차

1. 전체 hunk inventory와 cross-file contract graph를 먼저 만든다.
2. package/domain/runtime boundary로 shard한다. 파일 수만 균등 분할하지 않는다.
3. schema·API·event·shared type·migration은 생산자와 소비자 shard를 교차 연결한다.
4. shard diff를 prompt에 직접 담지 못하면 `review-execution.md` §1.5를 따른다.
   shard 파일은 `<snapshot>/agent-input/shard-<n>.diff`처럼 snapshot 하위에만 만든다.
   shard 이름은 저장소 안에서만 유일하므로, 시스템 temp에 두면 동시에 실행 중인
   다른 저장소의 shard와 같은 경로가 되어 reviewer가 남의 diff를 읽는다.
5. core 3명에게 domain shard와 Correctness, Security, Architecture 관점을
   겹쳐 배정하고 Testing, Reliability, UX, Migration, Requirements, Release,
   Domain trigger에 따라 specialist를 추가한다. 모든 shard에서 Line·Correctness
   coverage를 유지한다.
6. Security·Architecture owner는 개별 shard에 갇히지 않고 전체 contract graph를
   검토하며 관련 owner에게 `SendMessage`로 교차검증을 요청한다.
7. lead aggregator가 finding stable ID, 반론, 중복을 통합한다. shard 하나가
   끝날 때마다 그 shard의 판정을 `ledger.py record`로 즉시 적재한다. lead는
   판정을 컨텍스트에 누적하지 않는다.
8. 전체 diff의 삭제 동작, wrapper/proxy, public contract를 다시 확인한다.
   미검토 hunk가 0인지는 기억이 아니라 `ledger.py status`의 `complete`와
   `pending`으로 확인한다.

## 규모에 따른 관점 배분

threshold는 shard 수와 인원만 정한다. **무엇을 집중해서 볼지는 diff의 구성이 정한다.**

- 신규 추가 비중(`추가 / (추가 + 삭제)`)이 높으면 "삭제된 동작의 의미 보존"에서
  확인할 대상이 적다. 주 위험은 새로 생긴 public contract, 도달하지 않는 경로,
  과설계, 기존 코드와의 중복 구현으로 옮겨간다.
- 삭제 비중이 높으면 반대로 Line reviewer의 삭제 동작 추적과 wrapper/proxy 의미
  보존이 핵심이다.
- 어느 쪽이든 관점을 **빼지 않는다.** 같은 인원 안에서 배분만 바꾸고, 배분 근거를
  최종 보고에 남긴다.

## 제한

- shard 하나는 기본 25개 파일 또는 1000 changed lines 이하를 목표로 한다.
- generated/vendor는 원본과 생성 원인을 중심으로 축약할 수 있다.
- shard 경계를 넘는 finding을 한쪽에서만 종결하지 않는다.
- context 부족으로 읽지 못한 hunk는 `UNKNOWN`이며 성공을 차단한다.
- 대형 diff에서 원장은 선택이 아니다. 컨텍스트가 압축되면 판정 기억이 먼저
  사라지고, 그 결과 미검토 hunk가 차단이 아니라 침묵 통과가 된다.
