// Drag & drop for the upload page: dropped files are put into the normal file input.
const drop = document.getElementById("drop");
const input = document.getElementById("files");
const list = document.getElementById("file-list");

function showFiles() {
  list.innerHTML = "";
  for (const f of input.files) {
    const li = document.createElement("li");
    li.textContent = f.name + " (" + Math.round(f.size / 1024) + " KB)";
    list.appendChild(li);
  }
}

["dragenter", "dragover"].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", ev => { input.files = ev.dataTransfer.files; showFiles(); });
input.addEventListener("change", showFiles);
