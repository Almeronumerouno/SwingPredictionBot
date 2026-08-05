"use client";

import { useState } from "react";
import { toJpeg } from "html-to-image";
import jsPDF from "jspdf";

interface DownloadPdfButtonProps {
  targetId: string;
  fileName: string;
}

export default function DownloadPdfButton({ targetId, fileName }: DownloadPdfButtonProps) {
  const [isGenerating, setIsGenerating] = useState(false);

  const generatePDF = async () => {
    setIsGenerating(true);
    try {
      const element = document.getElementById(targetId);
      if (!element) {
        throw new Error("Element not found");
      }

      // Hide elements that shouldn't be printed by making them transparent 
      // (avoids layout shift compared to display:none)
      const noPrintElements = document.querySelectorAll(".no-print");
      const originalOpacities: string[] = [];
      noPrintElements.forEach((el, index) => {
        const htmlEl = el as HTMLElement;
        originalOpacities[index] = htmlEl.style.opacity;
        htmlEl.style.opacity = "0";
      });

      // Small delay to ensure DOM is ready and charts are fully rendered
      await new Promise((resolve) => setTimeout(resolve, 150));

      const dataUrl = await toJpeg(element, {
        quality: 0.8, // 80% quality JPEG reduces size significantly vs PNG
        pixelRatio: 2, // Keep resolution high for readability
        backgroundColor: "#ffffff",
      });

      // Restore hidden elements
      noPrintElements.forEach((el, index) => {
        (el as HTMLElement).style.opacity = originalOpacities[index];
      });

      // Calculate PDF dimensions (A4 size portrait)
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
      });

      const pdfWidth = pdf.internal.pageSize.getWidth();
      const imgProps = pdf.getImageProperties(dataUrl);
      const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

      // Add image to PDF (using JPEG compression)
      pdf.addImage(dataUrl, "JPEG", 0, 0, pdfWidth, pdfHeight, undefined, "FAST");
      
      // Handle multi-page if content is longer than one A4 page
      let heightLeft = pdfHeight - pdf.internal.pageSize.getHeight();
      let position = -pdf.internal.pageSize.getHeight();

      while (heightLeft > 0) {
        position = heightLeft - pdfHeight;
        pdf.addPage();
        pdf.addImage(dataUrl, "JPEG", 0, position, pdfWidth, pdfHeight, undefined, "FAST");
        heightLeft -= pdf.internal.pageSize.getHeight();
      }

      pdf.save(`${fileName}.pdf`);
    } catch (error) {
      console.error("Failed to generate PDF:", error);
      alert("Gagal membuat PDF. Silakan coba lagi.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <button
      onClick={generatePDF}
      disabled={isGenerating}
      className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:text-blue-800 font-bold rounded-xl transition-all duration-200 border border-blue-200 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed print:hidden no-print"
      title="Download sebagai PDF"
    >
      {isGenerating ? (
        <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      ) : (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      )}
      {isGenerating ? "Memproses..." : "Download PDF"}
    </button>
  );
}
