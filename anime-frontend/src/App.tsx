import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Home } from './pages/Home';
import { Detail } from './pages/Detail';
import { Search } from './pages/Search';
import { UserList } from './pages/UserList';
import { Auth } from './pages/Auth';

const qc = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <header className="flex gap-4 p-3 border-b border-anilist-border">
          <Link to="/">Home</Link><Link to="/search">Search</Link><Link to="/list">My List</Link><Link to="/auth/signin">Sign in</Link>
        </header>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/anime/:id" element={<Detail />} />
          <Route path="/search" element={<Search />} />
          <Route path="/list" element={<UserList />} />
          <Route path="/auth/signin" element={<Auth />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
