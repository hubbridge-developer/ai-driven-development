import { Box, Typography } from '@mui/material';
import { BRAND } from '../theme';

/**
 * The AIDD brand lockup: a gradient monogram tile + optional wordmark.
 * Used in the nav bar and can be reused on empty states / headers.
 */
export default function BrandMark({
  showName = true,
  size = 34,
}: {
  showName?: boolean;
  size?: number;
}) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
      <Box
        sx={{
          width: size,
          height: size,
          borderRadius: 2,
          background: BRAND.gradient,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: 900,
          fontSize: size * 0.4,
          letterSpacing: '-0.04em',
          boxShadow: '0 6px 16px rgba(124,58,237,0.35)',
          flexShrink: 0,
        }}
      >
        A
      </Box>
      {showName && (
        <Box sx={{ lineHeight: 1 }}>
          <Typography
            component="span"
            sx={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.02em', display: 'block' }}
          >
            {BRAND.short}
          </Typography>
          <Typography
            component="span"
            sx={{ fontSize: 11, color: 'text.secondary', display: 'block', mt: '1px' }}
          >
            {BRAND.name}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
