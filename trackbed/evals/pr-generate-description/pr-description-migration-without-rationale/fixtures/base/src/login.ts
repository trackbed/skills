import type { Database } from "./db";
import { verifyPassword } from "./password";

export async function login(
  db: Database,
  email: string,
  password: string,
): Promise<{ userId: string } | null> {
  const [user] = await db.query<{ id: string; password_hash: string }>(
    "SELECT id, password_hash FROM users WHERE lower(email) = lower($1)",
    [email],
  );
  if (!user || !(await verifyPassword(password, user.password_hash))) {
    return null;
  }
  return { userId: user.id };
}
