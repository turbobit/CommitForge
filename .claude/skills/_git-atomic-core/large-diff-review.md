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
4. core 3명에게 domain shard와 Correctness, Security, Architecture 관점을
   겹쳐 배정하고 Testing, Reliability, UX, Migration, Requirements, Release,
   Domain trigger에 따라 specialist를 추가한다. 모든 shard에서 Line·Correctness
   coverage를 유지한다.
5. Security·Architecture owner는 개별 shard에 갇히지 않고 전체 contract graph를
   검토하며 관련 owner에게 `SendMessage`로 교차검증을 요청한다.
6. lead aggregator가 finding stable ID, 반론, 중복과 hunk coverage를 통합한다.
7. 전체 diff의 삭제 동작, wrapper/proxy, public contract와 미검토 hunk 0을 다시 확인한다.

## 제한

- shard 하나는 기본 25개 파일 또는 1000 changed lines 이하를 목표로 한다.
- generated/vendor는 원본과 생성 원인을 중심으로 축약할 수 있다.
- shard 경계를 넘는 finding을 한쪽에서만 종결하지 않는다.
- context 부족으로 읽지 못한 hunk는 `UNKNOWN`이며 성공을 차단한다.
