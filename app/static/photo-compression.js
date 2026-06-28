const CLEANRUN_PHOTO_MAX_DIMENSION = 1600;
const CLEANRUN_PHOTO_QUALITY = 0.76;

function readOriginalFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function canvasToBlob(canvas, type, quality) {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), type, quality);
  });
}

async function compressImageFileToDataUrl(file) {
  if (!file || !file.type || !file.type.startsWith("image/")) {
    return readOriginalFileAsDataUrl(file);
  }

  return new Promise((resolve) => {
    const imageUrl = URL.createObjectURL(file);
    const image = new Image();

    image.onload = async () => {
      try {
        const scale = Math.min(
          1,
          CLEANRUN_PHOTO_MAX_DIMENSION / image.width,
          CLEANRUN_PHOTO_MAX_DIMENSION / image.height,
        );
        const width = Math.max(1, Math.round(image.width * scale));
        const height = Math.max(1, Math.round(image.height * scale));

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(image, 0, 0, width, height);

        const blob = await canvasToBlob(canvas, "image/jpeg", CLEANRUN_PHOTO_QUALITY);
        URL.revokeObjectURL(imageUrl);

        if (!blob) {
          resolve(readOriginalFileAsDataUrl(file));
          return;
        }

        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => resolve(readOriginalFileAsDataUrl(file));
        reader.readAsDataURL(blob);
      } catch (error) {
        URL.revokeObjectURL(imageUrl);
        resolve(readOriginalFileAsDataUrl(file));
      }
    };

    image.onerror = () => {
      URL.revokeObjectURL(imageUrl);
      resolve(readOriginalFileAsDataUrl(file));
    };

    image.src = imageUrl;
  });
}

fileToDataUrl = compressImageFileToDataUrl;

handleFiles = async function(files, input) {
  if (!files || files.length === 0) return [];
  const next = await Promise.all([...files].map(compressImageFileToDataUrl));
  if (input) input.value = "";
  return next;
};

handleCaptureFiles = async function(files, input) {
  const next = await handleFiles(files, input);
  state.photos.push(...next);
  renderThumbs();
  clearValidation();
  if (next.length) toast("Photo compressed and attached");
};

function bindCompressedPhotoInputs() {
  if ($("cameraInput")) $("cameraInput").onchange = (event) => handleCaptureFiles(event.target.files, event.target);
  if ($("libraryInput")) $("libraryInput").onchange = (event) => handleCaptureFiles(event.target.files, event.target);
}

bindCompressedPhotoInputs();
