import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = path.join(projectRoot, ".output", "public");
const distDir = path.join(projectRoot, "dist");
const server = (
  await import(pathToFileURL(path.join(projectRoot, ".output", "server", "index.mjs")).href)
).default;

await rm(distDir, { recursive: true, force: true });
await mkdir(distDir, { recursive: true });
await cp(publicDir, distDir, { recursive: true });

for (const route of ["/", "/exceptions", "/transactions"]) {
  const response = await server.fetch(
    new Request(`http://localhost${route}`),
    {},
    { waitUntil() {} },
  );
  if (!response.ok) {
    throw new Error(`Could not render frontend route ${route}: HTTP ${response.status}`);
  }

  const routeDir = route === "/" ? distDir : path.join(distDir, route.slice(1));
  await mkdir(routeDir, { recursive: true });
  await writeFile(path.join(routeDir, "index.html"), await response.text(), "utf8");
}
