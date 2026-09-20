# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Tô Anh Đức
**Nhóm:** G16
**Ngày:** 20/09/2026

> Báo cáo này ghi lại các phần đã thực hiện trong CP2, R2, CP3–CP4 và R3/CP6. Strategy cá nhân là Heading/Section kết hợp Recursive Chunking.

## 1. Khởi động (Warm-up) — Cá nhân

### Độ tương tự Cosine

Độ tương tự cosine cao nghĩa là hai vector có hướng gần nhau, nên hai đoạn text được embedding biểu diễn là gần nhau về ý nghĩa. Giá trị càng gần 1 thì mức tương đồng càng cao; hai vector vuông góc có giá trị gần 0.

**Ví dụ có độ tương tự CAO:**

- Câu A: `Người bán phải tiếp nhận yêu cầu bảo hành hợp lệ.`
- Câu B: `Seller is responsible for handling valid warranty requests.`
- Tại sao tương đồng: Hai câu diễn đạt cùng trách nhiệm của người bán dù khác ngôn ngữ và cách dùng từ.

**Ví dụ có độ tương tự THẤP:**

- Câu A: `Người bán phải tiếp nhận yêu cầu bảo hành hợp lệ.`
- Câu B: `Hệ thống chia văn bản thành các đoạn nhỏ để tìm kiếm.`
- Tại sao khác: Một câu nói về nghĩa vụ bảo hành, câu còn lại nói về chunking/retrieval.

Cosine similarity phù hợp với text embedding vì nó tập trung vào hướng của vector hơn là độ lớn tuyệt đối. Điều này giúp so sánh nội dung có độ dài khác nhau ổn định hơn khoảng cách Euclid.

### Bài toán tính toán Chunking

Với tài liệu 10.000 ký tự, `chunk_size=500`, `overlap=50`:

```text
ceil((10,000 - 50) / (500 - 50))
= ceil(9,950 / 450)
= ceil(22.11)
= 23 chunks
```

Nếu `overlap=100`:

```text
ceil((10,000 - 100) / (500 - 100))
= ceil(9,900 / 400)
= 25 chunks
```

Overlap lớn hơn làm tăng số chunk nhưng giữ lại nhiều ngữ cảnh giữa hai chunk liên tiếp, hữu ích khi thông tin quan trọng nằm gần ranh giới chia nhỏ.

## 2. Hướng tiếp cận của tôi (My Approach)

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`**

Mình dùng regex `(?<=[.!?])\s+` để tách sau dấu chấm, chấm than hoặc chấm hỏi nhưng vẫn giữ dấu câu trong câu trước. Text rỗng hoặc chỉ chứa whitespace trả về list rỗng; các câu sau đó được gom tối đa `max_sentences_per_chunk` câu vào một chunk. Edge case như chữ viết tắt (`TS.`) hoặc số thập phân vẫn có thể bị nhận diện sai vì đây là sentence splitter đơn giản.

**`RecursiveChunker.chunk` / `_split`**

Thuật toán chọn separator đầu tiên xuất hiện theo thứ tự `\n\n`, `\n`, `. `, space và separator rỗng. Ba base case là text rỗng, text đã ngắn hơn `chunk_size`, và không còn separator phù hợp thì chuyển sang fixed-size fallback. Với mảnh quá dài, `_split` gọi đệ quy bằng các separator cấp thấp hơn; các mảnh nhỏ liền kề được gom lại trước khi tạo chunk mới.

**`ChunkingStrategyComparator.compare`**

Comparator chạy `FixedSizeChunker`, `SentenceChunker` và `RecursiveChunker` trên cùng text, rồi trả về `count`, `avg_length` và danh sách `chunks` cho từng chiến lược. Cách này tạo baseline chung để nhóm so sánh sau này.

### R3 — Heading/Section strategy và baseline

Mình bổ sung `HeadingSectionChunker`: tách Markdown theo heading, giữ heading trong mỗi chunk; nếu một section dài thì dùng `RecursiveChunker` với kích thước còn lại sau phần heading. Ba chiến lược chốt cho R3 là `FixedSizeChunker(chunk_size=500, overlap=50)`, `SentenceChunker(max_sentences_per_chunk=3)` và `HeadingSectionChunker(chunk_size=500)`.

Baseline chạy trên ba tài liệu:

| Tài liệu | Strategy | Số chunk | Avg length | Max | Nhận xét |
|---|---|---:|---:|---:|---|
| TikTok trả hàng/hoàn tiền | Fixed 500/50 | 4 | 449.50 | 500 | Giữ lượng context lớn, có overlap; ít chunk vụn |
| TikTok trả hàng/hoàn tiền | Sentence 3 | 4 | 410.00 | 525 | Giữ ranh giới câu; một chunk vượt 500 do câu dài |
| TikTok trả hàng/hoàn tiền | Heading/Section | 7 | 239.86 | 437 | Giữ heading tốt; một số section ngắn tạo chunk nhỏ |
| Shopee bảo hành | Fixed 500/50 | 3 | 394.67 | 500 | Ổn định, nhưng có thể trộn nhiều mục trong một chunk |
| Shopee bảo hành | Sentence 3 | 3 | 359.67 | 431 | Đọc mạch lạc, giữ trọn câu |
| Shopee bảo hành | Heading/Section | 5 | 215.20 | 304 | Giữ cấu trúc mục, có chunk ngắn theo heading |
| Shopee hướng dẫn trả hàng | Fixed 500/50 | 2 | 466.50 | 500 | Chunk dài nhưng không bị quá vụn |
| Shopee hướng dẫn trả hàng | Sentence 3 | 5 | 175.40 | 323 | Nhiều chunk ngắn hơn, dễ mất context khi câu hỏi cần nhiều bước |
| Shopee hướng dẫn trả hàng | Heading/Section | 4 | 219.25 | 366 | Cân bằng cấu trúc và độ dài; có chunk ngắn chứa heading |

`ChunkingStrategyComparator().compare()` cũng đã chạy trên cùng ba tài liệu để đối chiếu baseline. Sau đó CP6 dùng backend thật `text-embedding-3-small`; output đầy đủ nằm trong `ket_qua_benchmark.txt`.

### Lớp EmbeddingStore

**`add_documents` + `search`**

Mỗi `Document` được chuyển thành record gồm `id`, `content`, bản sao `metadata` và embedding. Nếu metadata chưa có `doc_id`, store dùng `Document.id` làm `doc_id`. Search embedding query bằng cùng embedding function, tính dot product với embedding đã lưu và sắp xếp score giảm dần.

**`search_with_filter` + `delete_document`**

Metadata được lọc trước khi similarity search, tránh việc các record không phù hợp chiếm các vị trí top-k. `delete_document` xóa tất cả record có `metadata['doc_id']` trùng với `doc_id` được truyền vào và trả về `True` nếu có record bị xóa.

Trong CP4, mình giữ implementation in-memory theo yêu cầu lab, không thêm ChromaDB hoặc dependency mới.

### Tác tử KnowledgeBaseAgent

`answer` gọi `store.search(question, top_k)` để lấy các chunk liên quan, nối content thành context và đưa context cùng câu hỏi vào prompt. Prompt yêu cầu LLM chỉ dùng context được cung cấp và nói rõ khi context không đủ thông tin; sau đó gọi `llm_fn` và trả về kết quả.

## 3. Hoàn thiện code (Core Implementation)

### Kết quả kiểm thử

Đã chạy:

```text
pytest tests/ -v
============================= 42 passed in 0.09s =============================
```

**Số lượng bài test vượt qua:** **42 / 42**

Các phần đã hoàn thiện gồm `src/chunking.py`, `src/store.py` và `src/agent.py`. Ngoài ra, `main.py` được bổ sung cấu hình stdout UTF-8 để manual demo in được câu hỏi tiếng Việt trên Windows.

## 4. Dự đoán độ tương tự (Similarity Predictions)

Mình dùng `_mock_embed` để kiểm tra công thức vì không cần API key. Các điểm dưới đây kiểm tra đúng hàm cosine nhưng không đại diện cho chất lượng semantic production; mock sinh vector theo hash nên có thể cho kết quả bất ngờ.

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Người bán phải tiếp nhận yêu cầu bảo hành hợp lệ. | Người bán chịu trách nhiệm xử lý yêu cầu bảo hành hợp lệ. | cao | 0.0325 | Không theo mock |
| 2 | Người mua có 10 ngày để gửi sản phẩm trả. | Sản phẩm còn tem và phiếu bảo hành. | thấp | -0.1008 | Có |
| 3 | Yêu cầu được xử lý trong 3–5 ngày làm việc. | Thời gian xử lý yêu cầu thường là 3–5 ngày làm việc. | cao | -0.0246 | Không theo mock |
| 4 | Hoàn tiền toàn bộ chặn yêu cầu hậu mãi tiếp theo. | Người mua vẫn có thể gửi yêu cầu sau khi hoàn tiền một phần. | thấp | -0.0561 | Có |
| 5 | Người bán phải công bố chính sách bảo hành. | Vector store lưu embedding để tìm kiếm tương tự. | thấp | 0.0592 | Không theo mock |

Cặp 1 và cặp 3 bất ngờ vì được dự đoán cao nhưng điểm mock thấp. Điều này cho thấy `_mock_embed` phù hợp kiểm tra cấu trúc/công thức, không phù hợp để kết luận hai câu có gần nghĩa hay không.

## 5. Kết quả truy xuất của tôi (Competition Results)

Bộ 5 query và gold answer nằm trong [BENCHMARK_R2.md](BENCHMARK_R2.md). CP6 đã chạy bằng backend thật `text-embedding-3-small`; output đầy đủ nằm trong `ket_qua_benchmark.txt`. Bảng dưới đây dùng strategy cá nhân `heading_section` và query có metadata filter.

| # | Câu hỏi (Query) | Top-1 Chunk | Score | Relevant | Agent answer |
|---|---|---|---|---|---|
| 1 | Thời hạn người bán TikTok Shop xem xét yêu cầu | `tiktok-shop-return-refund-seller#3` | 0.720101 | Có trong top-3; section thời hạn ở top-3 | Đúng: 1 ngày; quá hạn có thể tự động phê duyệt |
| 2 | Thời hạn người mua gửi hàng trả trên TikTok Shop | `tiktok-shop-return-refund-seller#5` | 0.621606 | Có; top-1 chứa đúng 10 ngày và hậu quả | Thiếu: agent nêu 10 ngày nhưng bỏ sót gửi trễ thì yêu cầu bị đóng và không hoàn tiền |
| 3 | Khác nhau giữa hoàn tiền toàn bộ và một phần | `tiktok-shop-refund-proposal-seller#3` | 0.596977 | Có; top-1 chứa toàn bộ gold answer | Đúng: hoàn toàn bộ chặn yêu cầu tiếp theo; hoàn một phần vẫn cho phép yêu cầu |
| 4 | Điều kiện bảo hành và trách nhiệm người bán trên Shopee | `shopee-warranty-policy-both#1` | 0.776267 | Có trong top-3; top-1 chủ yếu chứa trách nhiệm | Thiếu: agent nêu trách nhiệm seller nhưng không nêu đủ điều kiện buyer |
| 5 | Thời gian xử lý và hoàn tiền của Shopee | `shopee-return-refund-guide-buyer#2` | 0.753351 | Có; top-1 chứa đúng 3–5 và 1–14 ngày | Đúng: xử lý 3–5 ngày; hoàn tiền 1–14 ngày tùy phương thức |

**Số câu hỏi có chunk liên quan trong top-3:** **5 / 5**

Điểm theo rubric là **8 / 10**: câu 1, 3 và 5 đạt 2 điểm; câu 2 và 4 đạt 1 điểm vì agent answer còn thiếu chi tiết trong gold answer. Retrieval backend và agent backend là hai lớp khác nhau: retrieval dùng embedding để xếp hạng chunk, còn agent dùng DeepSeek `deepseek-flash` để sinh câu trả lời từ context đã truy xuất.

DeepSeek đã gọi thành công cho đủ 5 query. Trong lần chạy hiện tại, môi trường thiếu `sentence_transformers`, nên runner báo `mock fallback`; các chunk đầu vào được lấy theo top-3 đã ghi nhận trong kết quả CP6. Vì vậy 8/10 là điểm agent answer đã kiểm tra; benchmark end-to-end với local embedding cần chạy lại trong environment có local model.

**Failure case thật:** Query 2 khi bỏ `metadata_filter` trả top-1 là `shopee-return-refund-guide-buyer#2`, trong khi gold answer thuộc TikTok Shop. Khi lọc `platform=tiktok_shop`, `audience=seller`, `category=return_refund`, chunk TikTok đúng được đưa lên top-1.

**Điều hay nhất tôi học được:**

Qua CP6, mình thấy Heading/Section giữ tốt cấu trúc chính sách nhưng vẫn có thể bị nhiễu khi query không dùng metadata filter. Metadata phải được lọc trước similarity search, còn gold answer phải được kiểm chứng trực tiếp từ corpus.

## Tự Đánh Giá (Kết quả hiện tại)

| Tiêu chí | Điểm tự đánh giá |
|----------|---:|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 8 / 10 |
| **Tổng phần cá nhân** | **58 / 60** |

### Ghi chú verify

- DeepSeek agent answer đã chạy đủ 5 query và được ghi trong `ket_qua_agent_answers.txt`.
- Nếu cần chốt benchmark end-to-end tuyệt đối, chạy lại runner trong environment có `sentence_transformers` để retrieval backend local và agent backend DeepSeek cùng một pipeline.
