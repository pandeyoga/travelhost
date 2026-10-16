import { Images } from "lucide-react";
import MediaBrowser from "@/components/media/MediaBrowser";

/**
 * MediaManager — halaman `/app/media`.
 *
 * Dibuat sebagai halaman tersendiri (bukan hanya modal di dalam editor iklan seperti sebelumnya)
 * karena mengelola aset adalah pekerjaan tersendiri: merapikan folder, mengganti foto armada yang
 * sudah diperbarui, memotong ulang gambar hero, dan membersihkan aset yang tidak terpakai. Semua itu
 * tidak terjadi "sambil" menyunting satu halaman — memaksanya lewat modal membuat pekerjaan rapi-rapi
 * itu tidak pernah dilakukan.
 *
 * Seluruh keadaan data (loading / kosong / galat + coba lagi) ditangani `MediaBrowser`.
 */
export default function MediaManager() {
  return (
    <div className="space-y-4" data-testid="media-page">
      <section className="rounded-[14px] border border-[#EDEEF1] bg-white px-4 py-3">
        <h2 className="flex items-center gap-2 text-[14px] font-bold text-[#1C1C1E]">
          <Images size={15} /> Media Library
        </h2>
        <p className="mt-0.5 text-[12px] text-[#6B6B73]">
          Satu tempat untuk semua foto &amp; video: website (destinasi, paket, artikel, testimoni) dan
          halaman iklan. Kelola folder, unduh, ganti berkas, potong ukuran, dan pilih banyak sekaligus.
          Mengganti berkas sebuah aset otomatis memperbarui semua halaman yang memakainya.
        </p>
      </section>
      <MediaBrowser mode="page" showImport />
    </div>
  );
}
