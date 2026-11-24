"""Dokumentasi dan visual berdasarkan hasil retrieval/LLM yang tersimpan."""
from pathlib import Path
import json


def md_escape(value):
    return str(value).replace('|','\\|').replace('\n',' ')


def results_markdown(root):
    import semantic_search as app
    results=json.loads((root/'documentation/query_results.json').read_text(encoding='utf-8'))
    review_path=root/'documentation/manual_reviews.json'
    reviews=json.loads(review_path.read_text(encoding='utf-8')) if review_path.is_file() else {}
    lines=['# Pengujian Relevansi Retrieval dan Response AI',
           '', 'Tujuh query ditetapkan sebelum pengambilan hasil. FAQ acuan adalah penilaian relevansi primer pada dataset mentor, bukan daftar seluruh FAQ yang mungkin relevan.',
           '', '| Query | Jenis | FAQ acuan | FAQ top-1 | Cosine | Status LLM |',
           '|---|---|---|---:|---:|---|']
    for r in results:
        lines.append(f"| {r['query_id']} | {r['kind']} | {r['expected_faq_ids'] or 'Tidak ada'} | {r['retrieved'][0]['faq_id']} | {r['retrieved'][0]['cosine_similarity']:.4f} | {r['status']} |")
    lines += ['', '## Hasil per query']
    reviewed=0
    for r in results:
        lines += ['',f"### {r['query_id']}: {r['kind']}", '',f"**Query:** {r['query']}",
                  '',f"**Perilaku yang diharapkan:** {r['expected_behavior']}",
                  '', '| Rank | FAQ | Category | Cosine similarity | Question |',
                  '|---:|---:|---|---:|---|']
        for item in r['retrieved']:
            lines.append(f"| {item['rank']} | {item['faq_id']} | {item['category']} | {item['cosine_similarity']:.4f} | {md_escape(item['question'])} |")
        lines += ['',f"**Jawaban Gemini:** {r['answer']}",
                  '',f"**Sumber yang digunakan:** {r['source_faq_ids'] or 'Tidak ada'}; **status:** `{r['status']}`."]
        record=reviews.get(r['query_id'],{})
        identity=app.fingerprint({'query':r['query'],'answer':r['answer'],'source_faq_ids':r['source_faq_ids']})
        if record.get('reviewed_answer_fingerprint') == identity:
            reviewed += 1
            lines += ['',f"**Analisis manual:** {record['analysis']}",
                      '',f"**Penilaian dukungan fakta:** {record['factual_assessment']}."]
        else:
            lines += ['', '**Analisis manual:** hasil ini belum ditinjau atau telah berubah setelah refresh. Bandingkan jawaban dengan FAQ context sebelum menyimpulkan kualitas faktual.']
    lines += ['', '## Metode dan batasan penelaahan', '',
              f'{reviewed}/{len(results)} respons saat ini cocok dengan fingerprint penelaahan manual yang disimpan. '
              'Penelaahan dilakukan saat penyusunan project dengan membandingkan jawaban terhadap FAQ sumber. '
              'Ini bukan audit independen atau metrik otomatis yang membuktikan semua jawaban benar. '
              'Validasi kode hanya menjamin schema dan ID sumber berada di context, bukan kebenaran seluruh klaim.',
              '', 'Hasil saat ini tidak membuktikan performa pada seluruh variasi pertanyaan, kebijakan yang berubah, atau semua prompt injection.']
    return '\n'.join(lines)+'\n',reviewed


def write_documentation(root):
    import semantic_search as app
    profile=json.loads((root/'documentation/knowledge_base_profile.json').read_text(encoding='utf-8'))
    report=json.loads((root/'documentation/evaluation_report.json').read_text(encoding='utf-8'))
    results=json.loads((root/'documentation/query_results.json').read_text(encoding='utf-8'))
    test_report, reviewed=results_markdown(root)
    reviews=json.loads((root/'documentation/manual_reviews.json').read_text(encoding='utf-8'))
    highlights=[]
    for result in results:
        review=reviews.get(result['query_id'],{})
        current=app.fingerprint({'query':result['query'],'answer':result['answer'],'source_faq_ids':result['source_faq_ids']})
        observation=review.get('analysis','Belum ditinjau.') if review.get('reviewed_answer_fingerprint') == current else 'Respons berubah atau belum ditinjau; perlu penelaahan manual baru.'
        highlights.append(f"- **{result['query_id']}:** {observation}")
    manual_highlights='\n'.join(highlights)
    (root/'documentation/retrieval_test_results.md').write_text(test_report,encoding='utf-8')
    table='\n'.join([
        '| Query | Jenis | FAQ top-1 | Cosine | Status |',
        '|---|---|---:|---:|---|',
        *[f"| {r['query_id']} | {r['kind']} | {r['retrieved'][0]['faq_id']} | {r['retrieved'][0]['cosine_similarity']:.4f} | {r['status']} |" for r in results]
    ])
    category_table='\n'.join(['| Kategori | Entri |','|---|---:|',
                             *[f'| {k} | {v} |' for k,v in profile['categories'].items()]])
    text=rf'''# Semantic Search & LLM Application

**Peserta:** Naufal Ahmad-C24  
**Repository:** `assignment-semantic-search-naufal-ahmad-c24`

Prototype asisten FAQ e-commerce: **ingest -> embed -> store -> retrieve -> generate**.
Embedding dan jawaban dihasilkan dengan Gemini API nyata. Index FAISS, vektor, mapping FAQ,
rekaman jawaban, dan notebook yang sudah dieksekusi disertakan dalam project.

## 1. Problem statement, sumber data, dan asumsi

Tim customer service ingin menjawab pertanyaan berulang seputar pemesanan, pengiriman,
pembayaran, pengembalian, akun, promo, produk, dan bantuan pelanggan. Objective prototype
adalah menemukan FAQ yang paling relevan meskipun kata-kata query berbeda, lalu
menyusun jawaban alami yang hanya didukung FAQ tersebut.

Sumber: knowledge base dan starter notebook dari mentor, *Individual Assignment -
Semantic Search & LLM Application*, AI Engineering Bootcamp. Tidak menggunakan knowledge
base lain. Isi FAQ diperlakukan sebagai kebijakan dalam studi kasus, bukan pernyataan
kebijakan suatu perusahaan nyata. Knowledge base asli disalin utuh ke `data/` dan tidak ditimpa.

Asumsi dan batasan: satu FAQ adalah satu unit retrievable; sistem tidak mengakses status
pesanan pribadi, cuaca, katalog aktual, atau kebijakan eksternal. Jika jawaban tidak ada atau
hanya sebagian tersedia pada context, sistem harus mengatakannya. Chunking dokumen panjang
dan UI web tidak menjadi kebutuhan minimum tugas ini; antarmuka disediakan lewat notebook dan CLI.

## 2. Kondisi dan pengolahan knowledge base

- Ukuran: **{profile['entries']} entri x 4 kolom**, dengan {len(profile['categories'])} kategori.
- Kolom: `faq_id`, `category`, `question`, `answer`.
- Missing values: **{profile['missing_cells']}**; duplikat penuh: **{profile['full_duplicates']}**; `faq_id` unik.
- Spasi awal/akhir dirapikan pada salinan DataFrame. CSV asli tidak diubah.
- Satu unit berisi `Q: question` dan `A: answer`. Tidak memisahkan pertanyaan dari jawaban
  atau mengganti FAQ dengan jawaban buatan.

{category_table}

SHA-256 CSV asli:

```text
{profile['raw_sha256']}
```

## 3. Tahapan pengerjaan dan konfigurasi sistem

1. **Ingest:** baca CSV dengan Pandas, periksa schema, missing, ID unik, serta kategori.
2. **Prepare:** gabungkan question + answer menjadi 59 unit; simpan mapping posisi ke `faq_id`.
3. **Embed:** kirim setiap unit secara terpisah ke **`{app.EMBED_MODEL}`**,
   `output_dimensionality={app.DIMENSION}`. Shape diperiksa: **(59, 768)**, dtype **float32**,
   seluruh nilai finite dan tidak ada vektor nol.
4. **Store:** normalisasikan L2, buat **FAISS IndexFlatIP**, dan simpan
   `artifacts/faq.index`. Jumlah vektor: **{report['index_vectors']}**, dimensi: **{report['embedding_dimension']}**.
5. **Retrieve:** buat query embedding dengan model/dimensi yang sama, normalisasikan,
   lalu ambil **top-3**. Posisi FAISS dipetakan kembali ke ID dan isi FAQ.
6. **Prompt:** susun **Persona, Task, Context, Format**, dengan FAQ hasil pencarian
   sebagai context. Jawaban test/FAQ acuan penguji tidak dikirim ke model sebagai label jawaban.
7. **Generate:** panggil **`{app.LLM_MODEL}`**, temperature **0.2**,
   thinking level **minimal**, `max_output_tokens=1024`, output JSON terstruktur.
8. **Evaluate:** uji tujuh query, simpan ranking/skor, jawaban, sumber dan analisis manual.
9. **Verify:** baca ulang index, cocokkan jumlah/mapping/hash, uji replay tanpa API key,
   dan jalankan seluruh cell notebook.

Model contoh lama `text-embedding-004` dan `gemini-2.0-flash` pada starter diganti
dengan model aktif yang telah diverifikasi. Struktur delapan section starter dipertahankan.

### Format embedding dan pengukuran similarity

Untuk Gemini Embedding 2, format input mengikuti petunjuk retrieval/QA Google:

```text
Dokumen: title: [question] | text: Q: [question] A: [answer]
Query:   task: question answering | query: [pertanyaan pengguna]
```

Setiap pemanggilan embedding berisi satu unit untuk menghindari agregasi beberapa FAQ
menjadi satu vektor pada Embedding 2. Ada 59 rekaman embedding dokumen dan 7 query embedding
nyata untuk demo. Embedding mentah disimpan pada `document_embeddings.npy`; salinannya
dinormalisasikan sebelum masuk index. **Tidak menggunakan TF-IDF atau vektor acak sebagai pengganti.**

Inner product pada dua vektor unit sama dengan cosine similarity. Skor lebih besar berarti
lebih dekat secara semantik; rentang teoretis -1 sampai 1. Skor ini **bukan probabilitas
jawaban benar**, confidence terkalibrasi, atau bukti bahwa context menjawab query.
Tidak ada threshold yang ditentukan dari tujuh query test; penolakan jawaban bergantung
pada pemeriksaan kecukupan context oleh LLM. Ini tetap memiliki keterbatasan.

## 4. Prompt dan integrasi jawaban

- **Persona:** asisten customer service e-commerce yang ramah, bahasa Indonesia.
- **Task:** menjawab hanya dari context; jangan mengisi rincian dengan pengetahuan umum.
- **Context:** ID FAQ, kategori, question, dan answer dari top-3 retrieval.
- **Format:** `answer`, `source_faq_ids`, serta status `answered`, `partial`, atau `not_available`.

System instruction memisahkan data FAQ/query dari instruksi. Model diarahkan untuk tidak
mengarang angka, daftar bank, kontak, syarat, atau kebijakan. Jika informasi tidak tersedia,
model mengakuinya dan menyarankan customer service. Informasi parsial tidak dinyatakan lengkap.

Validasi kode mengecek JSON, jawaban tidak kosong, status, dan apakah ID sumber termasuk
FAQ yang benar-benar ada dalam context. Jawaban `not_available` tidak boleh mengutip
sumber yang tidak mendukung. **Pengecekan ID tidak membuktikan factual grounding**;
karena itu hasil tetap ditelaah terhadap isi FAQ.

`generate_answer()` menggabungkan query embedding, pencarian FAISS, pembuatan prompt,
pemanggilan/replay Gemini, dan validasi. Detail prompt dan respons nyata dapat diperiksa
pada `documentation/llm_responses.json`.

## 5. Hasil pengujian

Set uji ditetapkan sebelum pengambilan hasil: **2 query langsung, 2 parafrasa,
1 di luar knowledge base, 1 dengan rincian yang belum tersedia, dan 1 instruksi menyesatkan**.
FAQ acuan tersimpan di `test_queries.json` sebagai kriteria uji, bukan input tambahan ke LLM.

{table}

Pada **{report['queries_with_primary_relevant_faq']} query dengan FAQ acuan relevan**:

| Metrik retrieval | Hasil |
|---|---:|
| Hit@1 | {report['hit_at_1']:.4f} |
| Hit@3 | {report['hit_at_3']:.4f} |
| MRR@3 | {report['mrr_at_3']:.4f} |

Hit@1/3 berarti FAQ acuan ditemukan pada peringkat pertama/tiga teratas; MRR@3 adalah
rata-rata kebalikan peringkat FAQ acuan, bernilai nol jika tidak ditemukan.
Q5 di luar FAQ tidak memiliki FAQ acuan sehingga dikeluarkan dari metrik ranking,
dan dinilai dari kemampuan mengakui keterbatasan. Nilai ini bukan accuracy global aplikasi.

![Skor top-1 retrieval](documentation/retrieval_scores.png)

Analisis lengkap berisi seluruh top-3, similarity score, jawaban dan penelaahan per query:
**[retrieval_test_results.md](documentation/retrieval_test_results.md)**.
Sebanyak **{reviewed}/{len(results)} respons saat ini** cocok dengan fingerprint penelaahan manual.
Penelaahan dilakukan saat penyusunan project, bukan oleh penilai independen.

## 6. Analisis penting dan keterbatasan

{manual_highlights}

- Top-3 dapat memuat FAQ yang hanya terkait sebagian. Context tambahan berisiko mengganggu
  jawaban; `top_k=3` dipilih sebagai baseline ringkas, tanpa tuning pada set uji.
- Hanya 59 FAQ dan 7 query buatan untuk pengujian terarah. Belum ada benchmark besar,
  penilai independen, pengujian bahasa/typo yang luas, atau kalibrasi threshold.
- LLM masih dapat salah menafsirkan context atau mengarang rincian pada query lain.
  Pengawasan kualitas dan eskalasi ke manusia tetap diperlukan sebelum penggunaan nyata.
- Model/API, kuota, dan jaringan menjadi dependensi. Temperature rendah tidak menjamin
  hasil identik. Refresh dapat mengubah jawaban; analisis manual lama ditandai bila fingerprint berubah.
- FAQ dapat berubah. Index/embedding perlu dibangun ulang ketika isi sumber berubah;
  pengecekan hash mencegah memakai index yang tidak sesuai dataset.
- Index exact cocok untuk ukuran prototype ini. Untuk skala besar diperlukan evaluasi
  penyimpanan, latency, akses data, dan teknik retrieval lanjutan.

## 7. Struktur project

```text
semantic-search-assignment/
|-- data/ecommerce_faq_knowledge_base.csv
|-- notebook/starter_notebook_semantic_search.ipynb
|-- src/semantic_search.py
|-- src/reporting.py
|-- tests/test_semantic_search.py
|-- artifacts/
|   |-- document_embeddings.npy
|   |-- embedding_metadata.json
|   |-- faq.index
|   |-- faq_metadata.json
|   |-- index_manifest.json
|   `-- query_embeddings.json
|-- documentation/
|   |-- application_config.json
|   |-- evaluation_report.json
|   |-- knowledge_base_profile.json
|   |-- llm_responses.json
|   |-- manual_reviews.json
|   |-- query_results.json
|   |-- retrieval_results.csv
|   |-- retrieval_test_results.md
|   |-- retrieval_scores.png
|   |-- system_flow.png
|   `-- test_queries.json
|-- .gitignore
|-- README.md
`-- requirements.txt
```

![Alur sistem](documentation/system_flow.png)

Seluruh artifact di atas perlu disertakan, khususnya **file index `faq.index`** dan script
pembuatannya. `.venv`, file `.env`, cache Python dan runtime notebook tidak diunggah.

## 8. Cara menjalankan

Lingkungan teruji: Python {report['runtime']['python']}, Pandas {report['runtime']['pandas']},
NumPy {report['runtime']['numpy']}, FAISS CPU {report['runtime']['faiss-cpu']},
Google GenAI {report['runtime']['google-genai']}. Semua dependency dikunci di `requirements.txt`.

### Instalasi baru (Windows PowerShell)

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### Menjalankan demo tanpa API key

Di folder lokal tugas, `.venv` sudah disiapkan:

```powershell
Set-Location 'D:/REWORK/Individual Assignment 3/semantic-search-assignment'
./.venv/Scripts/python.exe src/semantic_search.py
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Demo memakai embedding dokumen/query serta rekaman jawaban **dari panggilan Gemini nyata**,
bukan mock, keyword search, atau output yang dikarang. Walaupun API di-replay, pencarian
FAISS pada query embedding dan validasi context tetap dijalankan ulang.
Cache diikat pada model, format, dimensi, hash sumber, prompt, dan konfigurasi yang sesuai.

Untuk notebook, buka folder project di VS Code, pilih kernel Python `.venv`, lalu jalankan
**Restart Kernel and Run All**. `REFRESH_API=False` adalah default agar replay tidak memanggil API.
Notebook telah disimpan dengan output eksekusi dan analisis sehingga dapat dibaca di GitHub.

### Query baru, refresh API, atau rebuild index

Query demo yang sudah direkam dapat diulang tanpa key. Query baru memerlukan
`GEMINI_API_KEY` pada environment lokal agar dapat membuat embedding query dan jawaban baru.
Key tidak boleh ditulis di notebook, README atau repository. Pada notebook, jika refresh
dipilih dan key belum ada, gunakan input tersembunyi yang disediakan.

```powershell
./.venv/Scripts/python.exe src/semantic_search.py --query "Metode pembayaran apa saja yang tersedia?"
./.venv/Scripts/python.exe src/semantic_search.py --rebuild-index
./.venv/Scripts/python.exe src/semantic_search.py --refresh
```

`--rebuild-index` membuat ulang FAISS dari vektor yang sudah disimpan tanpa panggilan API.
`--refresh` membuat embedding dan jawaban baru menggunakan kuota akun; biaya bergantung
tier/model. Setelah refresh, tinjau ulang jawaban dan perbarui `manual_reviews.json` agar
analisis sesuai hasil terbaru. Demo tidak mengklaim tier akun gratis atau biaya aktual.

Linux/macOS dapat memakai `python3 -m venv .venv` serta `.venv/bin/python` dengan versi
Python dan dependency yang kompatibel. Pengujian project ini dilakukan pada Windows.

## 9. Pengumpulan dan pemetaan rubrik

| Komponen | Bukti dalam project |
|---|---|
| Problem statement (10%) | Objective, sumber FAQ, asumsi, dan batasan pada README/notebook |
| Embedding & vector database (20%) | Embedding nyata 59 x 768, FAISS 59 vektor, metadata, script rebuild |
| Semantic search (20%) | Fungsi query embedding + FAISS, top-3 dan similarity, uji parafrasa |
| Prompt & LLM (20%) | Persona/Task/Context/Format, integrasi Gemini nyata dan sumber jawaban |
| Uji & analisis (20%) | 7 query bervariasi, ranking, jawaban, metrik retrieval dan review manual |
| Dokumentasi (10%) | README, notebook dengan output, requirements dan cara menjalankan |

Nama repository: **`assignment-semantic-search-naufal-ahmad-c24`**. Unggah isi folder project
dan pastikan mentor dapat mengaksesnya. Periksa README, notebook, serta file index sudah
tersimpan, kemudian kumpulkan satu link repository melalui submission tugas 3.

## Referensi

- PDF dan starter notebook mentor: *Individual Assignment - Semantic Search & LLM Application*.
- [Gemini embedding, format retrieval dan normalisasi](https://aistudio.google.com/docs/embeddings).
- [Gemini Embedding 2 dan dimensi yang didukung](https://aistudio.google.com/docs/models/gemini-embedding-2).
- [FAISS IndexFlatIP](https://faiss.ai/cpp_api/struct/structfaiss_1_1IndexFlatIP.html).
- [FAISS: cosine similarity](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances).
- [Gemini 3.5 Flash-Lite](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite).
'''
    (root/'README.md').write_text(text,encoding='utf-8')
    make_visuals(root,results)
    return test_report


def make_visuals(root,results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw, ImageFont
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11})
    fig,ax=plt.subplots(figsize=(9.5,5.5),constrained_layout=True)
    values=[r['retrieved'][0]['cosine_similarity'] for r in results]
    labels=[f"{r['query_id']}  |  FAQ {r['retrieved'][0]['faq_id']}" for r in results]
    colors=['#B54B4B' if not r['expected_faq_ids'] else '#286D9F' for r in results]
    bars=ax.barh(labels,values,color=colors)
    ax.invert_yaxis()
    ax.bar_label(bars,fmt='%.3f',padding=5)
    ax.set(xlim=(0,1),xlabel='Cosine similarity (bukan probabilitas jawaban benar)',
           title='Skor kandidat FAQ teratas pada tujuh query uji')
    ax.spines[['top','right']].set_visible(False)
    fig.savefig(root/'documentation/retrieval_scores.png',dpi=180)
    plt.close(fig)

    image=Image.new('RGB',(1800,760),'#F4F7FB')
    draw=ImageDraw.Draw(image)
    font_dir=Path('C:/Windows/Fonts')
    def font(size,bold=False):
        path=font_dir/('arialbd.ttf' if bold else 'arial.ttf')
        return ImageFont.truetype(str(path),size) if path.is_file() else ImageFont.truetype('DejaVuSans.ttf',size)
    def text(x,y,value,size=25,bold=False,color='#23364F'):
        draw.text((x,y),value,font=font(size,bold),fill=color)
    text(65,48,'Alur Semantic Search dan Jawaban FAQ',48,True)
    text(68,121,'59 FAQ  |  Gemini Embedding 2  |  FAISS  |  Gemini 3.5 Flash-Lite',27)
    titles=['INGEST','EMBED','STORE','RETRIEVE','GENERATE']
    bodies=[['59 FAQ dari CSV','Question + answer','Data asli tetap utuh'],
            ['Gemini API nyata','59 x 768 float32','Input per entri FAQ'],
            ['Normalisasi L2','FAISS IndexFlatIP','Index + mapping ID'],
            ['Query embedding','Top-3 cosine score','FAQ paling dekat'],
            ['Prompt + context','Jawaban + sumber','Akui jika tidak ada']]
    for i,(title,body) in enumerate(zip(titles,bodies)):
        x=65+i*340
        draw.rounded_rectangle((x,225,x+310,502),radius=18,fill='white',outline='#CFD9E6',width=2)
        text(x+24,254,title,29,True)
        for j,line in enumerate(body):
            text(x+24,329+j*42,line,23)
        if i<4:
            draw.line((x+316,363,x+333,363),fill='#64768C',width=4)
            draw.polygon([(x+335,363),(x+325,354),(x+325,372)],fill='#64768C')
    draw.rounded_rectangle((65,558,1735,690),radius=15,fill='#E5EDF6')
    text(92,579,'Saat dipakai: pertanyaan -> embedding query -> retrieval -> prompt -> jawaban',27,True)
    text(92,628,'Skor dekat tidak selalu berarti FAQ menjawab query; jawaban harus didukung context.',25)
    image.save(root/'documentation/system_flow.png',optimize=True)


if __name__=='__main__':
    write_documentation(Path(__file__).resolve().parents[1])
