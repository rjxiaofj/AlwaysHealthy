#!/usr/bin/env node
/**
 * 打包体积守卫。
 *
 * 上一次靠手工发现 echarts 占掉 466 kB，删掉之后没有东西拦着它再回来。
 * 这里把「首屏要下多少 JS」「单个 chunk 最大多少」变成可失败的检查：
 * 超了就让 CI 红，逼着改的人做一次决定（真需要这么大，就调预算并写清原因）。
 *
 * 用法：npm run size        # 检查，超预算退出码 1
 *      npm run size -- --report  # 只打印实测值，不判预算（调预算时用）
 */

import { gzipSync } from 'node:zlib'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = join(ROOT, 'dist')
const BUDGET_FILE = join(ROOT, 'bundle-budget.json')

const kB = (bytes) => bytes / 1024
const fmt = (bytes) => kB(bytes).toFixed(1).padStart(6)

if (!existsSync(DIST)) {
  console.error('没有 dist/，先跑 npm run build')
  process.exit(1)
}

const assetsDir = join(DIST, 'assets')
const files = readdirSync(assetsDir)
const jsFiles = files.filter((name) => name.endsWith('.js'))
const cssFiles = files.filter((name) => name.endsWith('.css'))

function gzipSize(file) {
  return gzipSync(readFileSync(join(assetsDir, file)), { level: 9 }).length
}

const measured = [...jsFiles, ...cssFiles].map((name) => ({
  name,
  raw: readFileSync(join(assetsDir, name)).length,
  gzip: gzipSize(name),
}))

// 首屏 = index.html 里直接引用的那些（entry 与 modulepreload）。路由 chunk 不算，
// 它们要等用户点进去才下
const html = readFileSync(join(DIST, 'index.html'), 'utf8')
const referenced = new Set([...html.matchAll(/\/assets\/([\w.-]+\.(?:js|css))/g)].map((match) => match[1]))
const firstLoad = measured.filter((file) => referenced.has(file.name))

const sum = (list) => list.reduce((total, file) => total + file.gzip, 0)
const largest = [...measured.filter((file) => file.name.endsWith('.js'))].sort((left, right) => right.gzip - left.gzip)[0]

const actual = {
  firstLoad: sum(firstLoad),
  totalJs: sum(measured.filter((file) => file.name.endsWith('.js'))),
  totalCss: sum(measured.filter((file) => file.name.endsWith('.css'))),
  singleChunk: largest ? largest.gzip : 0,
}

console.log('\n实测体积（gzip）\n')
console.log('  文件                                              raw kB  gzip kB')
for (const file of measured.sort((left, right) => right.raw - left.raw)) {
  const mark = referenced.has(file.name) ? '首屏' : '    '
  console.log(`  ${mark} ${file.name.padEnd(48)} ${fmt(file.raw)} ${fmt(file.gzip)}`)
}

console.log('\n汇总（gzip）\n')
for (const [key, value] of Object.entries(actual)) {
  console.log(`  ${key.padEnd(12)} ${fmt(value)} kB`)
}
if (largest) console.log(`  最大 JS       ${largest.name}`)

if (process.argv.includes('--report')) {
  console.log('\n--report 模式，不判预算\n')
  process.exit(0)
}

if (!existsSync(BUDGET_FILE)) {
  console.error('\n缺少 bundle-budget.json')
  process.exit(1)
}

const budget = JSON.parse(readFileSync(BUDGET_FILE, 'utf8'))
const failures = []

for (const [key, limit] of Object.entries(budget)) {
  if (typeof limit !== 'number' || !(key in actual)) continue
  if (actual[key] > limit * 1024) {
    failures.push(`${key}: ${kB(actual[key]).toFixed(1)} kB > 预算 ${limit} kB`)
  }
}

if (failures.length) {
  console.error('\n超出打包预算：')
  for (const line of failures) console.error(`  - ${line}`)
  console.error('\n真的需要这么大，就改 bundle-budget.json 并在提交信息里写清原因；')
  console.error('只是想看看现在多少，跑 npm run size -- --report\n')
  process.exit(1)
}

const headroom = Object.entries(budget)
  .filter(([key, limit]) => typeof limit === 'number' && key in actual)
  .map(([key, limit]) => `${key} 还剩 ${(limit - kB(actual[key])).toFixed(1)} kB`)

console.log(`\n在预算内（${headroom.join('，')}）\n`)
