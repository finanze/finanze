import { exec } from "child_process"
import util from "util"

const execPromise = util.promisify(exec)

const TARGET_PROCESS_PREFIX = "finanze-server"

interface ProcessInfo {
  pid: number
  name: string
}

/**
 * Finds and terminates all processes on Windows whose name starts with a specific prefix.
 */
export async function findAndKillProcesses() {
  const listCommand = "wmic process get Name,ProcessId /format:csv"
  const { stdout } = await execPromise(listCommand)

  if (!stdout) {
    return
  }

  const processesToKill = stdout
    .trim()
    .split("\n")
    .slice(1)
    .map(line => {
      const parts = line.split(",")
      if (parts.length < 3) return null
      return {
        name: parts[1],
        pid: parseInt(parts[2], 10),
      }
    })
    .filter(
      proc =>
        proc &&
        proc.name &&
        proc.pid &&
        proc.name.startsWith(TARGET_PROCESS_PREFIX),
    ) as Array<ProcessInfo>

  if (processesToKill.length === 0) {
    console.log(`No target processes to kill.`)
    return
  }

  console.log(`Killing ${processesToKill.map(p => p.pid).join(", ")}`)

  const killPromises = processesToKill.map(proc => {
    const killCommand = `taskkill /f /t /pid ${proc.pid}`
    return execPromise(killCommand)
      .then(() => console.log(`Terminated #${proc.pid}`))
      .catch(err =>
        console.error(
          `Failed to terminate ${proc.name} (PID: ${
            proc.pid
          }): ${err.message.trim()}`,
        ),
      )
  })

  await Promise.all(killPromises)
}
