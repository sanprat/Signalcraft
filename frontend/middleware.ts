import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
    const token = request.cookies.get('sc_token')?.value || request.headers.get('x-sc-token')
    const isAdmin = request.cookies.get('sc_admin')?.value === 'true'

    const publicPaths = ['/login', '/register', '/pricing', '/admin/login', '/api/auth']
    const adminPaths = ['/admin']

    const isPublicPath = publicPaths.some(path => request.nextUrl.pathname.startsWith(path))
    const isAdminPath = adminPaths.some(path => request.nextUrl.pathname.startsWith(path))

    // Protect admin routes
    if (isAdminPath && !request.nextUrl.pathname.startsWith('/admin/login')) {
        if (!isAdmin || !token) {
            return NextResponse.redirect(new URL('/admin/login', request.url))
        }
    }

    // Protect regular routes
    if (!isAdminPath && !token && !isPublicPath && request.nextUrl.pathname !== '/') {
        return NextResponse.redirect(new URL('/login', request.url))
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico|api/).*)'],
}