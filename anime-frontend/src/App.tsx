import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Home } from './pages/Home';
import { Detail } from './pages/Detail';
import { Search } from './pages/Search';
import { UserList } from './pages/UserList';
import { Auth } from './pages/Auth';
import { Chat } from './pages/Chat';
import { Genres } from './pages/Genres';
import { Browse } from './pages/Browse';
import { UI_VI } from './i18n/genres';

const qc = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <header className="flex gap-4 p-3 border-b border-anilist-border">
          <Link to="/">{UI_VI.home}</Link><Link to="/genres">{UI_VI.genres}</Link><Link to="/browse">{UI_VI.browse}</Link><Link to="/top">{UI_VI.top}</Link><Link to="/search">{UI_VI.search}</Link><Link to="/chat">Ask AI</Link><Link to="/list">{UI_VI.myList}</Link><Link to="/auth/signin">{UI_VI.signIn}</Link>
        </header>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/anime/:id" element={<Detail />} />
          <Route path="/search" element={<Search />} />
          <Route path="/genres" element={<Genres />} />
          <Route path="/genre/:name" element={<Browse />} />
          <Route path="/browse" element={<Browse />} />
          <Route path="/top" element={<Browse />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/list" element={<UserList />} />
          <Route path="/auth/signin" element={<Auth />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
