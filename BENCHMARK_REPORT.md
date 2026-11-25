# Benchmark & Observability Report — Day 14

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
|---|---:|---|
| p95 latency `/ask` | <= 500 ms | Giữ 95% yêu cầu tương tác ở mức phản hồi nhanh. |
| Error rate `/ask` | <= 2% | Bảo vệ trải nghiệm người dùng trước lỗi upstream. |
| Accuracy trên golden dataset | >= 100% | Golden dataset nhỏ (23 câu) nên dùng quality gate không regression. |

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Môi trường: Windows + Docker Desktop; agent v2 chạy local trên port 8002. Mỗi hàng dùng 300 request. File nguồn nằm trong `reports/`.

### 2.1 Concurrency vs latency

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.69 | 223.7 | 388.3 | 1694.4 | 0.00% | PASS |
| 10 | 27.19 | 245.8 | 921.2 | 1733.1 | 0.00% | FAIL (p95) |
| 50 | 20.05 | 1495.6 | 5938.8 | 7391.2 | 0.00% | FAIL (p95) |
| 100 | 19.01 | 4004.8 | 10282.1 | 12876.4 | 0.00% | FAIL (p95) |

RPS tăng từ concurrency 1 lên 10, nhưng không tăng tuyến tính sau đó. Một process local phải xếp hàng nhiều request đồng thời; phần tail latency của mock LLM làm hàng đợi và p95/p99 tăng mạnh.

### 2.2 Tail latency

Mỗi hàng dùng concurrency 20 và 300 request.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 239.2 | 531.4 | 583.5 |
| 0.03 | 278.6 | 544.3 | 1730.0 |
| 0.1 | 402.9 | 1718.7 | 1794.0 |

p99 nhạy nhất với request chậm vì nó đại diện cho đuôi phân phối. Average che khuất một nhóm người dùng phải chờ rất lâu, do đó không nên dùng average làm SLO chính.

## 3. Benchmark chất lượng (`eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---:|---:|---:|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.4 | 109.0 | 115.0 |
| Tổng cost (USD) | 0.000408 | 0.000760 | 0.000802 |
| Cost / câu đúng (USD) | 0.00040815 | 0.00003619 | 0.00003488 |
| Quality gate | FAIL | PASS | PASS |

Hai câu v2 trả lời sai ban đầu là `security-02` và `scaling-03`. Tôi bổ sung hai entry knowledge base: JWT/API key (token, hết hạn, chữ ký) và Kubernetes HPA (CPU, memory, custom metrics). Lần eval cuối đạt 23/23, không có regression so với `eval_v2.json`.

Trade-off: v2 dùng retrieval nên tốn token, chi phí và latency cao hơn v1, nhưng chi phí cho mỗi câu đúng thấp hơn rất nhiều vì độ chính xác cải thiện rõ rệt.

Quality gate có thể chặn merge bằng lệnh:

```bash
python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 \
  --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json
```

Lệnh trả exit code khác 0 khi accuracy dưới ngưỡng hoặc có regression.

## 4. Observability stack (production)

Stack local đã chạy Grafana, Prometheus, Jaeger và agent. Trong thí nghiệm kết hợp `MOCK_ERROR_RATE=0.2`, `MOCK_SLOW_RATE=0.3`, Locust 30 users, Prometheus ghi nhận đồng thời `AgentHighErrorRate` và `AgentHighLatencyP95` ở trạng thái firing. Mẫu quan sát cho thấy error rate khoảng 19.9% và p95 khoảng 1.90 s; đây là kết quả của thí nghiệm kết hợp, không tách riêng tác động từng biến. Alert error bắt đầu pending lúc 12:49:52 UTC với `for: 1m`, alert latency lúc 12:49:57 UTC với `for: 2m`; chưa đo chính xác thời điểm firing từ lúc thay đổi cấu hình.

Evidence: [Grafana dashboard](screenshots/grafana-dashboard.png), [two firing alerts](screenshots/prometheus-alert-firing.png), [Jaeger trace list](screenshots/jaeger-traces.png), [slow trace](screenshots/jaeger-slow-trace.png) and [error trace](screenshots/jaeger-error-trace.png). The screenshots show a later experiment than the JSON and logs below: slow trace `8e2fef01115b13122b630bd81065bf93` (about 1.7 s) and error trace `2c182b71cfcc357049ee3dc344374f2f` (HTTP 503). The JSON and logs below document separate earlier traces.

Một request chậm được tạo có kiểm soát (`MOCK_SLOW_RATE=1`, `MOCK_ERROR_RATE=0`) trả 200, với header trace ID khớp log. Jaeger xác nhận trace `c3086b5894800cbe15bebbe639de1fe0`: span gốc `POST /ask` 1677.422 ms; span con chậm nhất `chat mock-llm-small` 1651.878 ms (98.5% tổng thời gian). Log tương ứng ghi HTTP 1676.3 ms và LLM 1652.4 ms:

```json
{"event":"llm_call","trace_id":"c3086b5894800cbe15bebbe639de1fe0","span_id":"d96fe3dde1ccd101","request_id":"942ac7c4b1a0","model":"mock-llm-small","llm_ms":1652.4}
```

Trace lỗi được tạo bằng `MOCK_ERROR_RATE=1`: request trả 503, trace ID `9ef4614d32858dd77c491ff84bdbbc3f`. Jaeger ghi event `exception` trên span `chat mock-llm-small` với `utils.mock_llm.LLMError`; dữ liệu nằm tại `reports/trace_error.json`. Log ứng dụng khớp trace ID:

```json
{"event":"llm_error","trace_id":"9ef4614d32858dd77c491ff84bdbbc3f","span_id":"7a4f35130b0bb9c8","request_id":"02d548ec44bf","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production, Locust)

Locust headless, 100 users, 2 phút; bảng lấy hàng `POST /ask` trong các file CSV tại `benchmark-results/` (percentile là giá trị xấp xỉ của Locust):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 1 | 34.66 | 970 | 3500 | 7300 | 47 / 4107 (1.14%) |
| 3 | 56.05 | 210 | 1400 | 1900 | 60 / 6683 (0.90%) |

Trong hai lượt đo này, 3 instance có p95 thấp hơn và RPS cao hơn. Đây là kết quả trên cùng máy local nhưng tải máy và hành vi mock ngẫu nhiên thay đổi theo thời gian, nên chưa đủ để kết luận quan hệ nhân quả chính xác hoặc khẳng định nút thắt duy nhất. Các lỗi 503 phù hợp với fault injection của mock.

## 6. Kết luận

1. Concurrency tăng không bảo đảm throughput tăng tuyến tính; p95/p99 bộc lộ hiện tượng queueing tốt hơn average.
2. Eval có baseline bắt được regression, còn quality gate giúp ngăn bản chất lượng thấp vào nhánh chính.
3. Retrieval tăng chi phí mỗi request nhưng giảm mạnh chi phí trên mỗi câu trả lời đúng.

Nếu triển khai production, tôi sẽ bổ sung synthetic external check, alert cho availability ở tầng load balancer, và theo dõi chất lượng/eval theo phiên bản agent.
