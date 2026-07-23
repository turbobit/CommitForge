# 대규모 Diff 리뷰

기본 threshold 중 하나를 넘으면 shard mode를 사용한다.

- 변경 파일 40개
- hunk 200개
- 추가+삭제 3000줄

`.commitforge/review.yml`이 더 엄격한 값을 지정하면 해당 값을 사용한다.

## 절차

1. 전체 hunk inventory와 cross-file contract graph를 먼저 만든다.
2. package/domain/runtime boundary로 shard한다. 파일 수만 균등 분할하지 않는다.
3. schema·API·event·shared type·migration은 소비자 shard와 교차 연결한다.
4. 각 shard에서 Line·Correctness와 관련 전문 reviewer를 실행한다.
5. Security와 Architecture는 전체 graph를 기준으로 별도 실행한다.
6. aggregator가 finding stable ID를 통합하고 hunk coverage를 합산한다.
7. 전체 diff의 삭제 동작, wrapper/proxy, public contract와 미검토 hunk 0을 다시 확인한다.

## 제한

- shard 하나는 기본 25개 파일 또는 1000 changed lines 이하를 목표로 한다.
- generated/vendor는 원본과 생성 원인을 중심으로 축약할 수 있다.
- shard 경계를 넘는 finding을 한쪽에서만 종결하지 않는다.
- context 부족으로 읽지 못한 hunk는 `UNKNOWN`이며 성공을 차단한다.
