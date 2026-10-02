import { initializeApp } from 'firebase/app'
import { getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut } from 'firebase/auth'

export const authDisabled = import.meta.env.VITE_AUTH_DISABLED === 'true'

let auth = null
if (!authDisabled) {
  const app = initializeApp({
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
  })
  auth = getAuth(app)
}

export function watchUser(cb) {
  if (authDisabled) {
    cb({ email: 'local-dev' })
    return () => {}
  }
  return onAuthStateChanged(auth, cb)
}

export const login = (email, password) => signInWithEmailAndPassword(auth, email, password)
export const logout = () => (auth ? signOut(auth) : Promise.resolve())
export const idToken = async () => (auth?.currentUser ? auth.currentUser.getIdToken() : null)
