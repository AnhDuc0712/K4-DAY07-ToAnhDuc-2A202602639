# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** G16
**Thành viên:** Phạm Anh Minh; Vũ Bá Anh; Hồ Hoàng Phương Anh; Tô Anh Đức
**Ngày:** 20/09/2026

> Báo cáo nhóm gồm lựa chọn tài liệu, thiết kế chiến lược, chất lượng truy xuất và demo. Phần cá nhân được trình bày riêng trong `REPORT_CANHAN.md`.

**Tổng điểm phần nhóm:** 40 = Document Set Quality (10) + Strategy Design (15) + Retrieval Quality (10) + Demo (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — 10 điểm

### Chủ đề và lý do chọn

**Chủ đề:** Chính sách bảo hành và hậu mãi dành cho người bán trên Shopee và TikTok Shop.

Corpus tập trung vào trả hàng, hoàn tiền, bảo hành, thời hạn xử lý và trách nhiệm người bán. Đây là các nội dung có điều kiện và con số cụ thể, phù hợp để kiểm thử semantic retrieval và metadata filter theo nền tảng, đối tượng và category.

### Data inventory

Số ký tự dưới đây tính toàn bộ file Markdown, gồm frontmatter và nội dung đã làm sạch.

| # | Tài liệu | Source URL | Retrieved / version | Ký tự | Metadata chính |
|---:|---|---|---|---:|---|
| 1 | TikTok Shop — Trả hàng và Hoàn tiền | [Seller University](https://seller-vn.tiktok.com/university/essay?course_type=1&from=search&identity=1&knowledge_id=1766935302801169&role=1) | 2026-09-20 / 2026-08-21 | 1965 | `tiktok_shop`, `seller`, `return_refund` |
| 2 | TikTok Shop — Đề nghị hoàn tiền cho khách hàng | [Seller University](https://seller-vn.tiktok.com/university/essay?knowledge_id=7997606615877377&lang=vi-VN) | 2026-09-20 / 2025-08-13 | 1272 | `tiktok_shop`, `seller`, `return_refund` |
| 3 | TikTok Shop — Chính sách cửa hàng tại Việt Nam | [Seller University](https://seller-vn.tiktok.com/university/essay?knowledge_id=761396473562887&lang=vi-VN) | 2026-09-20 / 2026-08-17 | 1698 | `tiktok_shop`, `seller`, `seller_policy` |
| 4 | Shopee — Quy định chung về Trả hàng/Hoàn tiền | [Shopee Help](https://help.shopee.vn/portal/4/article/188931-%5BTr%E1%BA%A3-h%C3%A0ng/Ho%C3%A0n-ti%E1%BB%81n%5D-Nh%E1%BB%AFng-quy-%C4%91%E1%BB%8Bnh-chung-v%E1%BB%81-Tr%E1%BA%A3-h%C3%A0ng/Ho%C3%A0n-ti%E1%BB%81n-c%E1%BB%A7a-Shopee) | 2026-09-20 / undated | 1427 | `shopee`, `both`, `return_refund` |
| 5 | Shopee — Hướng dẫn gửi yêu cầu Trả hàng/Hoàn tiền | [Shopee Help](https://help.shopee.vn/portal/4/article/79233) | 2026-09-20 / undated | 1136 | `shopee`, `buyer`, `return_refund` |
| 6 | Shopee — Chính sách bảo hành sản phẩm | [Shopee Help](https://help.shopee.vn/portal/4/article/77245) | 2026-09-20 / undated | 1331 | `shopee`, `both`, `warranty` |

**Data governance checklist:**

- [x] Có 6 tài liệu, nằm trong phạm vi 5–10 tài liệu.
- [x] Nguồn là trang chính thức của Shopee hoặc TikTok Shop.
- [x] Không dùng link sản phẩm, livestream, quảng cáo, blog cá nhân hoặc nội dung yêu cầu đăng nhập.
- [x] Không chứa API key, dữ liệu cá nhân hoặc thông tin đăng nhập.
- [x] Mỗi file có đầy đủ `source_url`, `retrieved_at`, `document_version`.
- [x] Có tài liệu `buyer`, `seller` và hai tài liệu gần chủ đề nhưng khác audience.

### Metadata schema

| Trường | Ví dụ | Vai trò trong retrieval |
|---|---|---|
| `platform` | `shopee`, `tiktok_shop` | Giới hạn kết quả theo sàn. |
| `audience` | `seller`, `buyer`, `both` | Tránh trộn chính sách cho người bán và người mua. |
| `category` | `return_refund`, `warranty` | Lọc theo loại chính sách. |
| `language` | `vi` | Xác định ngôn ngữ corpus. |
| `source_url` | URL Help/Seller University | Truy vết về nguồn chính thức. |
| `retrieved_at` | `2026-09-20` | Theo dõi thời điểm thu thập. |
| `document_version` | `2026-08-21` hoặc `undated` | Phân biệt phiên bản khi nguồn công bố ngày cập nhật. |
| `doc_id` / `chunk_id` | `file-stem` / `2` | Truy vết chunk về file gốc. |

---

## 2. Thiết kế chiến lược (Strategy Design) — 15 điểm

### Baseline trên cùng bộ tài liệu

| Tài liệu | Fixed-size 500/50 | Sentence 3 câu | Heading/Section + Recursive |
|---|---:|---:|---:|
| TikTok trả hàng/hoàn tiền | 4 chunk, avg 449.50 | 4 chunk, avg 410.00 | 7 chunk, avg 239.86 |
| Shopee bảo hành | 3 chunk, avg 394.67 | 3 chunk, avg 359.67 | 5 chunk, avg 215.20 |
| Shopee hướng dẫn trả hàng | 2 chunk, avg 466.50 | 5 chunk, avg 175.40 | 4 chunk, avg 219.25 |

Fixed-size có kích thước đều và overlap giúp giữ ngữ cảnh nhưng có thể cắt ngang điều khoản. Sentence giữ ranh giới câu tự nhiên nhưng kích thước không ổn định. Heading/Section tạo chunk nhỏ hơn, giữ tên mục và dùng RecursiveChunker khi section dài.

### Chiến lược của thành viên

**Phạm Anh Minh — Fixed-size baseline**

- `FixedSizeChunker(chunk_size=500, overlap=50)`.
- Mục đích: tạo baseline dễ so sánh, kích thước ổn định và giảm mất ngữ cảnh ở ranh giới chunk.
- Điểm yếu: có thể cắt ngang câu hoặc ghép hai mục chính sách khác nhau.

**Vũ Bá Anh — Sentence baseline**

- `SentenceChunker(max_sentences_per_chunk=3)`.
- Mục đích: giữ ranh giới câu tự nhiên để các điều kiện và thời hạn ngắn không bị cắt giữa câu.
- Điểm yếu: độ dài chunk không ổn định; một câu dài có thể làm chunk vượt kích thước mục tiêu.

**Hồ Hoàng Phương Anh — Heading/Section + Recursive**

- Tách nội dung theo Markdown heading `#`, `##`, `###` và giữ heading trong chunk.
- Section dài được tách tiếp bằng `RecursiveChunker`, đồng thời gắn heading vào từng chunk con.
- Lý do chọn: chính sách có cấu trúc theo các mục như “Thời hạn”, “Điều kiện”, “Trách nhiệm” và “Quy trình”; giữ heading giúp retrieval trả về đúng ngữ cảnh điều khoản.
- Đây là **chiến lược tốt nhất của nhóm** vì cân bằng được cấu trúc chính sách, độ đầy đủ ngữ nghĩa và khả năng truy vết nguồn.

**Tô Anh Đức — Tích hợp Recursive, EmbeddingStore, Agent và benchmark**

- Phụ trách hoàn thiện `RecursiveChunker`, `EmbeddingStore`, `KnowledgeBaseAgent`, benchmark và phần kiểm chứng retrieval.
- Recursive fallback được tích hợp trong Heading/Section để xử lý section dài mà không làm mất heading.
- Vai trò này tập trung vào tích hợp và đánh giá end-to-end, không tạo thêm một strategy cạnh tranh ngoài ba strategy benchmark đã thống nhất.

### So sánh chiến lược

| Chiến lược | Điểm mạnh | Điểm yếu | Vai trò trong nhóm |
|---|---|---|---|
| Fixed-size 500/50 | Đơn giản, kích thước ổn định, có overlap. | Có thể cắt giữa điều khoản. | Baseline của Phạm Anh Minh. |
| Sentence 3 câu | Giữ ranh giới câu, dễ đọc. | Chunk quá ngắn hoặc quá dài tùy câu. | Baseline của Vũ Bá Anh. |
| Heading/Section + Recursive | Giữ heading, điều khoản và ngữ cảnh; section dài vẫn được giới hạn. | Có thể tạo một số chunk ngắn theo heading. | **Chiến lược tốt nhất của Hồ Hoàng Phương Anh.** |
| Tích hợp Recursive/benchmark | Kiểm chứng fallback, metadata filter và agent answer trên cùng pipeline. | Phụ thuộc chất lượng corpus và embedding backend. | Phần tích hợp của Tô Anh Đức. |

**Kết luận chiến lược:** Heading/Section + Recursive là lựa chọn tốt nhất cho corpus chính sách. Nó phù hợp hơn với cấu trúc điều khoản so với cắt theo ký tự hoặc chỉ theo số câu, đồng thời hỗ trợ citation và truy vết section rõ ràng.

---

## 3. Benchmark và chất lượng truy xuất — 10 điểm

### Bộ query và gold answer

Năm query, gold answer và source section được kiểm chứng trong [BENCHMARK_R2.md](BENCHMARK_R2.md).

| # | Nội dung gold answer | Source |
|---:|---|---|
| 1 | Seller TikTok xem xét trong 1 ngày; quá hạn có thể tự động phê duyệt. | `tiktok-shop-return-refund-seller.md` |
| 2 | Người mua có 10 ngày; gửi trễ thì yêu cầu đóng và không hoàn tiền. | `tiktok-shop-return-refund-seller.md` |
| 3 | Hoàn toàn bộ chặn yêu cầu tiếp theo; hoàn một phần vẫn cho phép và tổng hoàn không vượt giá trị đơn. | `tiktok-shop-refund-proposal-seller.md` |
| 4 | Seller tiếp nhận/công bố bảo hành; buyer cần đáp ứng điều kiện bảo hành của nguồn. | `shopee-warranty-policy-both.md` |
| 5 | Xử lý 3–5 ngày; hoàn tiền 1–14 ngày tùy phương thức thanh toán. | `shopee-return-refund-guide-buyer.md` |

### Kết quả Heading/Section bằng local embedding

Backend retrieval: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Output đầy đủ: [ket_qua_benchmark_local.txt](../ket_qua_benchmark_local.txt).

| # | Top-1 sau filter | Score | Top-3 có nguồn liên quan? | Chấm theo gold |
|---:|---|---:|---|---:|
| 1 | `tiktok-shop-return-refund-seller#3` | 0.7685 | Có, nhưng chi tiết 1 ngày nằm ngoài top-1 | 1/2 |
| 2 | `tiktok-shop-return-refund-seller#5` | 0.6702 | Có, top-1 chứa đủ 10 ngày và hậu quả | 2/2 |
| 3 | `tiktok-shop-refund-proposal-seller#0` | 0.5999 | Có, chunk chứa đáp án ở top-3 | 2/2 |
| 4 | `shopee-warranty-policy-both#1` | 0.8008 | Có, top-3 có trách nhiệm nhưng thiếu điều kiện cụ thể | 1/2 |
| 5 | `shopee-return-refund-guide-buyer#2` | 0.8334 | Có, top-1 chứa đủ thời hạn | 2/2 |

**Điểm retrieval/agent hiện có:** **8/10**. Query 2 và 5 đạt đầy đủ; Query 1 và 4 còn thiếu một phần chi tiết trong top-1/context. Agent answer DeepSeek đã được kiểm tra riêng trong [ket_qua_agent_answers.txt](../ket_qua_agent_answers.txt).

### Metadata filter

Filter được áp dụng trước similarity search. Failure case rõ nhất là Query 2 khi bỏ filter: top-1 có thể chuyển sang tài liệu Shopee; khi dùng `platform=tiktok_shop`, `audience=seller`, `category=return_refund`, TikTok chunk đúng được đưa lên top-1. Điều này cho thấy filter làm tăng precision theo đúng đối tượng và nền tảng.

### Phân biệt hai backend

- **Retrieval backend:** local multilingual embedding tạo vector và `EmbeddingStore` xếp hạng chunk.
- **Agent backend:** DeepSeek `deepseek-flash` nhận query cùng context top-k để sinh câu trả lời có citation.

Hai backend độc lập nhưng phải dùng chung context đã truy xuất; lỗi DeepSeek không làm mất evidence retrieval.

---

## 4. Thuyết trình (Demo) và bài học nhóm — 5 điểm

**Flow demo:** mở `app.py` → hệ thống tự index 6 tài liệu → chọn Shopee/TikTok Shop và audience → hỏi bằng chat → xem câu trả lời → mở “Xem nguồn tham khảo” để kiểm tra chunk và URL gốc.

**Insights trình bày:**

1. Heading/Section + Recursive phù hợp với chính sách vì bảo toàn tên mục và ngữ cảnh điều khoản.
2. Metadata filter phải chạy trước similarity search; nếu lọc sau top-k, tài liệu sai audience có thể chiếm các vị trí cần thiết.
3. Đánh giá RAG phải kiểm tra cả chunk và nội dung agent answer, không chỉ kiểm tra `doc_id`.

**Bài học nhóm:** cùng corpus nhưng chunking khác nhau làm thay đổi số chunk, độ dài và vị trí câu trả lời. Vì vậy nhóm thống nhất benchmark, embedding backend, filter và gold answer trước khi so sánh.

**Nếu làm lại:** nhóm sẽ chạy local embedding và benchmark ngay sau khi chốt corpus, lưu output A/B có/không filter vào một file duy nhất và thêm AppTest cho các flow UI quan trọng.

---

## Tự đánh giá phần nhóm

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Document Set Quality | 10 / 10 |
| Strategy Design | 15 / 15 |
| Retrieval Quality | 8 / 10 |
| Demo | 5 / 5 |
| **Tổng phần nhóm** | **38 / 40** |

**Trạng thái nộp:** Corpus validator pass, 42 tests pass, local embedding pass, benchmark local đã lưu, UI V2 đã startup thành công. Không commit hoặc push trong bước này.
